//! JSON Export Helper

#[macro_use]
extern crate clap;
extern crate diesel;
extern crate dotenv;
#[macro_use]
extern crate error_chain;
extern crate fatcat;
extern crate fatcat_api_spec;
#[macro_use]
extern crate slog;
extern crate slog_async;
extern crate slog_term;
extern crate uuid;
extern crate crossbeam_channel;
extern crate serde_json;
extern crate num_cpus;

use clap::{App, Arg};
use slog::{Drain, Logger};
use dotenv::dotenv;
use std::env;

use diesel::prelude::*;
use diesel::r2d2::ConnectionManager;
use fatcat_api_spec::models::*;
use std::str::FromStr;
use uuid::Uuid;
use fatcat::ConnectionPool;
use fatcat::api_helpers::*;
use fatcat::api_entity_crud::*;
use fatcat::errors::*;

use std::thread;
//use std::io::{Stdout,StdoutLock};
use crossbeam_channel as channel;
//use num_cpus; TODO:
use std::io::prelude::*;
use std::io::{BufReader, BufWriter};

const CHANNEL_BUFFER_LEN: usize = 200;

arg_enum!{
    #[derive(PartialEq, Debug, Clone, Copy)]
    pub enum ExportEntityType {
        Creator,
        Container,
        File,
        Release,
        Work
    }
}

struct IdentRow {
    ident_id: FatCatId,
    rev_id: Option<Uuid>,
    redirect_id: Option<FatCatId>,
}

/// Instantiate a new API server with a pooled database connection
pub fn database_worker_pool() -> Result<ConnectionPool> {
    dotenv().ok();
    let database_url = env::var("DATABASE_URL").expect("DATABASE_URL must be set");
    let manager = ConnectionManager::<PgConnection>::new(database_url);
    let pool = diesel::r2d2::Pool::builder()
        .build(manager)
        .expect("Failed to create database pool.");
    Ok(pool)
}

macro_rules! generic_loop_work {
    ($fn_name:ident, $entity_model:ident) => {
        fn $fn_name(row_receiver: channel::Receiver<IdentRow>, output_sender: channel::Sender<String>, db_conn: &DbConn, expand: Option<ExpandFlags>) -> Result<()> {
            for row in row_receiver {
                let mut entity = $entity_model::db_get_rev(db_conn, row.rev_id.expect("valid, non-deleted row"))?;
                //let mut entity = ReleaseEntity::db_get_rev(db_conn, row.rev_id.expect("valid, non-deleted row"))?;
                entity.state = Some("active".to_string()); // XXX
                entity.ident = Some(row.ident_id.to_string());
                if let Some(expand) = expand {
                    entity.db_expand(db_conn, expand)?;
                }
                output_sender.send(serde_json::to_string(&entity)?);
            }
            Ok(())
        }
    }
}

generic_loop_work!(loop_work_container, ContainerEntity);
generic_loop_work!(loop_work_creator, CreatorEntity);
generic_loop_work!(loop_work_file, FileEntity);
generic_loop_work!(loop_work_release, ReleaseEntity);
generic_loop_work!(loop_work_work, WorkEntity);

fn loop_printer(output_receiver: channel::Receiver<String>, done_sender: channel::Sender<()>) -> Result<()> {
    let output = std::io::stdout();
    // XXX should log...
    // let mut buf_output = BufWriter::new(output.lock());
    let mut buf_output = BufWriter::new(output);
    for line in output_receiver {
        buf_output.write_all(&line.into_bytes())?;
        buf_output.write(b"\n")?;
        buf_output.flush()?;
    }
    drop(done_sender);
    Ok(())
}

fn parse_line(s: String) -> Result<IdentRow> {
    let fields: Vec<String> = s.split("\t").map(|v| v.to_string()).collect();
    if fields.len() != 3 {
        bail!("Invalid input line");
    }
    Ok(IdentRow {
        ident_id: FatCatId::from_uuid(&Uuid::from_str(&fields[0])?),
        rev_id: Some(Uuid::from_str(&fields[1])?),
        redirect_id: None,
    })
}

#[test]
fn test_parse_line() {
    assert!(false)
}

// Use num_cpus/2, or CLI arg for worker count
//
// 1. open buffered reader, buffered writer, and database pool. create channels
// 2. spawn workers:
//      - get a database connection from database pool
//      - iterate over row channel, pushing Strings to output channel
//      - exit when end of rows
// 3. spawn output printer
// 4. read rows, pushing to row channel
//      => every N lines, log to stderr
// 5. wait for all channels to finish, and quit
pub fn do_export(num_workers: usize, expand: Option<ExpandFlags>, entity_type: ExportEntityType) -> Result<()> {

    let db_pool = database_worker_pool()?;
    let buf_input = BufReader::new(std::io::stdin());
    let (row_sender, row_receiver) = channel::bounded(CHANNEL_BUFFER_LEN);
    let (output_sender, output_receiver) = channel::bounded(CHANNEL_BUFFER_LEN);
    let (done_sender, done_receiver) = channel::bounded(0);

    // Start row worker threads
    assert!(num_workers > 0);
    for _ in 0..num_workers {
        let db_conn = db_pool.get().expect("database pool");
        let row_receiver = row_receiver.clone();
        let output_sender = output_sender.clone();
        match entity_type {
            ExportEntityType::Container =>
                thread::spawn(move || loop_work_container(row_receiver, output_sender, &db_conn, expand)),
            ExportEntityType::Creator =>
                thread::spawn(move || loop_work_creator(row_receiver, output_sender, &db_conn, expand)),
            ExportEntityType::File =>
                thread::spawn(move || loop_work_file(row_receiver, output_sender, &db_conn, expand)),
            ExportEntityType::Release =>
                thread::spawn(move || loop_work_release(row_receiver, output_sender, &db_conn, expand)),
            ExportEntityType::Work =>
                thread::spawn(move || loop_work_work(row_receiver, output_sender, &db_conn, expand)),
        };
    }
    drop(output_sender);
    // Start printer thread
    thread::spawn(move || loop_printer(output_receiver, done_sender));

    for line in buf_input.lines() {
        let line = line?;
        let row = parse_line(line)?;
        row_sender.send(row);
    }
    drop(row_sender);
    done_receiver.recv();
    Ok(())
}

fn run() -> Result<()> {

    let m = App::new("fatcat-export")
        .version(env!("CARGO_PKG_VERSION"))
        .author("Bryan Newbold <bnewbold@archive.org>")
        .about("Fast exports of database entities from an id list")
        .args_from_usage(
            "-f --workers=[workers] 'number of threads (database connections) to use'
             --expand=[expand] 'sub-entities to include in dump'
             <entity_type> 'what entity type the idents correspond to'")
        .after_help("Reads a ident table TSV dump from stdin (aka, ident_id, rev_id, redirect_id), \
            and outputs JSON (one entity per line). Database connection info read from environment \
            (DATABASE_URL, same as fatcatd).")
        .get_matches();

    let num_workers: usize = match m.value_of("workers") {
        Some(v) => value_t_or_exit!(m.value_of("workers"), usize),
        None => std::cmp::min(1, num_cpus::get() / 2) as usize,
    };
    let expand = match m.value_of("expand") {
        Some(s) => Some(ExpandFlags::from_str(&s)?),
        None => None,
    };

    do_export(
        num_workers,
        expand,
        value_t_or_exit!(m.value_of("entity_type"), ExportEntityType),
    )
}

quick_main!(run);
