#!/usr/bin/env python3

import os, sys, argparse
import raven

from fatcat_tools import authenticated_api
from fatcat_tools.importers import *


# Yep, a global. Gets DSN from `SENTRY_DSN` environment variable
sentry_client = raven.Client()


def run_crossref(args):
    fci = CrossrefImporter(args.api,
        args.issn_map_file,
        extid_map_file=args.extid_map_file,
        edit_batch_size=args.batch_size,
        bezerk_mode=args.bezerk_mode)
    if args.kafka_mode:
        KafkaJsonPusher(
            fci,
            args.kafka_hosts,
            args.kafka_env,
            "api-crossref",
            "fatcat-{}-import-crossref".format(args.kafka_env),
            consume_batch_size=args.batch_size,
        ).run()
    else:
        JsonLinePusher(fci, args.json_file).run()

def run_jalc(args):
    ji = JalcImporter(args.api,
        args.issn_map_file,
        extid_map_file=args.extid_map_file)
    Bs4XmlLinesPusher(ji, args.xml_file, "<rdf:Description").run()

def run_arxiv(args):
    ari = ArxivRawImporter(args.api,
        edit_batch_size=args.batch_size)
    if args.kafka_mode:
        raise NotImplementedError
        #KafkaBs4XmlPusher(
        #    ari,
        #    args.kafka_hosts,
        #    args.kafka_env,
        #    "api-arxiv",
        #    "fatcat-{}-import-arxiv".format(args.kafka_env),
        #).run()
    else:
        Bs4XmlFilePusher(ari, args.xml_file, "record").run()

def run_pubmed(args):
    pi = PubmedImporter(args.api,
        args.issn_map_file,
        edit_batch_size=args.batch_size,
        do_updates=args.do_updates,
        lookup_refs=(not args.no_lookup_refs))
    if args.kafka_mode:
        raise NotImplementedError
        #KafkaBs4XmlPusher(
        #    pi,
        #    args.kafka_hosts,
        #    args.kafka_env,
        #    "api-pubmed",
        #    "fatcat-{}import-arxiv".format(args.kafka_env),
        #).run()
    else:
        Bs4XmlLargeFilePusher(
            pi,
            args.xml_file,
            "PubmedArticle",
            record_list_tag="PubmedArticleSet",
        ).run()

def run_jstor(args):
    ji = JstorImporter(args.api,
        args.issn_map_file,
        edit_batch_size=args.batch_size)
    Bs4XmlFileListPusher(ji, args.list_file, "article").run()

def run_orcid(args):
    foi = OrcidImporter(args.api,
        edit_batch_size=args.batch_size)
    JsonLinePusher(foi, args.json_file).run()

def run_journal_metadata(args):
    fii = JournalMetadataImporter(args.api,
        edit_batch_size=args.batch_size)
    JsonLinePusher(fii, args.json_file).run()

def run_chocula(args):
    fii = ChoculaImporter(args.api,
        edit_batch_size=args.batch_size,
        do_updates=args.do_updates)
    JsonLinePusher(fii, args.json_file).run()

def run_matched(args):
    fmi = MatchedImporter(args.api,
        edit_batch_size=args.batch_size,
        editgroup_description=args.editgroup_description_override,
        default_link_rel=args.default_link_rel,
        default_mimetype=args.default_mimetype)
    JsonLinePusher(fmi, args.json_file).run()

def run_arabesque_match(args):
    if (args.sqlite_file and args.json_file) or not (args.sqlite_file or
            args.json_file):
        print("Supply one of --sqlite-file or --json-file")
    ami = ArabesqueMatchImporter(args.api,
        editgroup_description=args.editgroup_description_override,
        do_updates=args.do_updates,
        require_grobid=(not args.no_require_grobid),
        extid_type=args.extid_type,
        crawl_id=args.crawl_id,
        default_link_rel=args.default_link_rel,
        edit_batch_size=args.batch_size)
    if args.sqlite_file:
        SqlitePusher(ami, args.sqlite_file, "crawl_result",
            ARABESQUE_MATCH_WHERE_CLAUSE).run()
    elif args.json_file:
        JsonLinePusher(ami, args.json_file).run()

def run_ingest_file(args):
    ifri = IngestFileResultImporter(args.api,
        editgroup_description=args.editgroup_description_override,
        skip_source_whitelist=args.skip_source_whitelist,
        do_updates=args.do_updates,
        default_link_rel=args.default_link_rel,
        require_grobid=(not args.no_require_grobid),
        edit_batch_size=args.batch_size)
    if args.kafka_mode:
        KafkaJsonPusher(
            ifri,
            args.kafka_hosts,
            args.kafka_env,
            "ingest-file-results",
            "fatcat-{}-ingest-file-result".format(args.kafka_env),
            kafka_namespace="sandcrawler",
            consume_batch_size=args.batch_size,
        ).run()
    else:
        JsonLinePusher(ifri, args.json_file).run()

def run_savepapernow_file(args):
    ifri = SavePaperNowFileImporter(args.api,
        editgroup_description=args.editgroup_description_override,
        edit_batch_size=args.batch_size)
    if args.kafka_mode:
        KafkaJsonPusher(
            ifri,
            args.kafka_hosts,
            args.kafka_env,
            "ingest-file-results",
            "fatcat-{}-savepapernow-file-result".format(args.kafka_env),
            kafka_namespace="sandcrawler",
            consume_batch_size=args.batch_size,
        ).run()
    else:
        JsonLinePusher(ifri, args.json_file).run()

def run_grobid_metadata(args):
    fmi = GrobidMetadataImporter(args.api,
        edit_batch_size=args.batch_size,
        longtail_oa=args.longtail_oa,
        bezerk_mode=args.bezerk_mode)
    LinePusher(fmi, args.tsv_file).run()

def run_shadow_lib(args):
    fmi = ShadowLibraryImporter(args.api,
        edit_batch_size=100)
    JsonLinePusher(fmi, args.json_file).run()

def run_wayback_static(args):
    api = args.api

    # find the release
    if args.release_id:
        release_id = args.release_id
    elif args.extid:
        idtype = args.extid.split(':')[0]
        extid = ':'.join(args.extid.split(':')[1:])
        if idtype == "doi":
            release_id = api.lookup_release(doi=extid).ident
        elif idtype == "pmid":
            release_id = api.lookup_release(pmid=extid).ident
        elif idtype == "wikidata":
            release_id = api.lookup_release(wikidata_qid=extid).ident
        else:
            raise NotImplementedError("extid type: {}".format(idtype))
    else:
        raise Exception("need either release_id or extid argument")

    # create it
    (editgroup_id, wc) = auto_wayback_static(api, release_id, args.wayback_url,
        editgroup_id=args.editgroup_id)
    if not wc:
        return
    print("release_id: {}".format(release_id))
    print("editgroup_id: {}".format(editgroup_id))
    print("webcapture id: {}".format(wc.ident))
    print("link: https://fatcat.wiki/webcapture/{}".format(wc.ident))

def run_cdl_dash_dat(args):
    api = args.api

    # create it
    (editgroup_id, release, fs) = auto_cdl_dash_dat(api, args.dat_path,
        release_id=args.release_id, editgroup_id=args.editgroup_id)
    if not fs:
        return
    print("release_id: {}".format(release.ident))
    print("editgroup_id: {}".format(editgroup_id))
    print("fileset id: {}".format(fs.ident))
    print("link: https://fatcat.wiki/fileset/{}".format(fs.ident))

def run_datacite(args):
    dci = DataciteImporter(args.api,
        args.issn_map_file,
        edit_batch_size=args.batch_size,
        bezerk_mode=args.bezerk_mode,
        debug=args.debug,
        extid_map_file=args.extid_map_file,
        insert_log_file=args.insert_log_file)
    if args.kafka_mode:
        KafkaJsonPusher(
            dci,
            args.kafka_hosts,
            args.kafka_env,
            "api-datacite",
            "fatcat-{}-import-datacite".format(args.kafka_env),
            consume_batch_size=args.batch_size,
        ).run()
    else:
        JsonLinePusher(dci, args.json_file).run()

def main():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--host-url',
        default="http://localhost:9411/v0",
        help="connect to this host/port")
    parser.add_argument('--kafka-hosts',
        default="localhost:9092",
        help="list of Kafka brokers (host/port) to use")
    parser.add_argument('--kafka-env',
        default="dev",
        help="Kafka topic namespace to use (eg, prod, qa)")
    parser.add_argument('--batch-size',
        help="size of batch to send",
        default=50, type=int)
    parser.add_argument('--editgroup-description-override',
        help="editgroup description override",
        default=None, type=str)
    subparsers = parser.add_subparsers()

    sub_crossref = subparsers.add_parser('crossref',
        help="import Crossref API metadata format (JSON)")
    sub_crossref.set_defaults(
        func=run_crossref,
        auth_var="FATCAT_AUTH_WORKER_CROSSREF",
    )
    sub_crossref.add_argument('json_file',
        help="crossref JSON file to import from",
        default=sys.stdin, type=argparse.FileType('r'))
    sub_crossref.add_argument('issn_map_file',
        help="ISSN to ISSN-L mapping file",
        default=None, type=argparse.FileType('r'))
    sub_crossref.add_argument('--extid-map-file',
        help="DOI-to-other-identifiers sqlite3 database",
        default=None, type=str)
    sub_crossref.add_argument('--no-lookup-refs',
        action='store_true',
        help="skip lookup of references (PMID or DOI)")
    sub_crossref.add_argument('--kafka-mode',
        action='store_true',
        help="consume from kafka topic (not stdin)")
    sub_crossref.add_argument('--bezerk-mode',
        action='store_true',
        help="don't lookup existing DOIs, just insert (clobbers; only for fast bootstrap)")

    sub_jalc = subparsers.add_parser('jalc',
        help="import JALC DOI metadata from XML dump")
    sub_jalc.set_defaults(
        func=run_jalc,
        auth_var="FATCAT_AUTH_WORKER_JALC",
    )
    sub_jalc.add_argument('xml_file',
        help="Jalc RDF XML file (record-per-line) to import from",
        default=sys.stdin, type=argparse.FileType('r'))
    sub_jalc.add_argument('issn_map_file',
        help="ISSN to ISSN-L mapping file",
        default=None, type=argparse.FileType('r'))
    sub_jalc.add_argument('--extid-map-file',
        help="DOI-to-other-identifiers sqlite3 database",
        default=None, type=str)

    sub_arxiv = subparsers.add_parser('arxiv',
        help="import arxiv.org metadata from XML files")
    sub_arxiv.set_defaults(
        func=run_arxiv,
        auth_var="FATCAT_AUTH_WORKER_ARXIV",
    )
    sub_arxiv.add_argument('xml_file',
        help="arXivRaw XML file to import from",
        default=sys.stdin, type=argparse.FileType('r'))
    sub_arxiv.add_argument('--kafka-mode',
        action='store_true',
        help="consume from kafka topic (not stdin)")

    sub_pubmed = subparsers.add_parser('pubmed',
        help="import MEDLINE/PubMed work-level metadata (XML)")
    sub_pubmed.set_defaults(
        func=run_pubmed,
        auth_var="FATCAT_AUTH_WORKER_PUBMED",
    )
    sub_pubmed.add_argument('xml_file',
        help="Pubmed XML file to import from",
        default=sys.stdin, type=argparse.FileType('r'))
    sub_pubmed.add_argument('issn_map_file',
        help="ISSN to ISSN-L mapping file",
        default=None, type=argparse.FileType('r'))
    sub_pubmed.add_argument('--no-lookup-refs',
        action='store_true',
        help="skip lookup of references (PMID or DOI)")
    sub_pubmed.add_argument('--do-updates',
        action='store_true',
        help="update pre-existing release entities")
    sub_pubmed.add_argument('--kafka-mode',
        action='store_true',
        help="consume from kafka topic (not stdin)")

    sub_jstor = subparsers.add_parser('jstor',
        help="import JSTOR work-level metadata from XML dump")
    sub_jstor.set_defaults(
        func=run_jstor,
        auth_var="FATCAT_AUTH_WORKER_JSTOR",
    )
    sub_jstor.add_argument('list_file',
        help="List of JSTOR XML file paths to import from",
        default=sys.stdin, type=argparse.FileType('r'))
    sub_jstor.add_argument('issn_map_file',
        help="ISSN to ISSN-L mapping file",
        default=None, type=argparse.FileType('r'))

    sub_orcid = subparsers.add_parser('orcid',
        help="import creator entities from ORCID XML dump")
    sub_orcid.set_defaults(
        func=run_orcid,
        auth_var="FATCAT_AUTH_WORKER_ORCID"
    )
    sub_orcid.add_argument('json_file',
        help="orcid JSON file to import from (or stdin)",
        default=sys.stdin, type=argparse.FileType('r'))

    sub_journal_metadata = subparsers.add_parser('journal-metadata',
        help="import/update container metadata from old manual munging format")
    sub_journal_metadata.set_defaults(
        func=run_journal_metadata,
        auth_var="FATCAT_AUTH_WORKER_JOURNAL_METADATA",
    )
    sub_journal_metadata.add_argument('json_file',
        help="Journal JSON metadata file to import from (or stdin)",
        default=sys.stdin, type=argparse.FileType('r'))

    sub_chocula = subparsers.add_parser('chocula',
        help="import/update container metadata from chocula JSON export")
    sub_chocula.set_defaults(
        func=run_chocula,
        auth_var="FATCAT_AUTH_WORKER_JOURNAL_METADATA",
    )
    sub_chocula.add_argument('json_file',
        help="chocula JSON entities file (or stdin)",
        default=sys.stdin, type=argparse.FileType('r'))
    sub_chocula.add_argument('--do-updates',
        action='store_true',
        help="update pre-existing container entities")

    sub_matched = subparsers.add_parser('matched',
        help="add file entities matched against existing releases; custom JSON format")
    sub_matched.set_defaults(
        func=run_matched,
        auth_var="FATCAT_API_AUTH_TOKEN",
    )
    sub_matched.add_argument('json_file',
        help="JSON file to import from (or stdin)",
        default=sys.stdin, type=argparse.FileType('r'))
    sub_matched.add_argument('--default-mimetype',
        default=None,
        help="default mimetype for imported files (if not specified per-file)")
    sub_matched.add_argument('--bezerk-mode',
        action='store_true',
        help="don't lookup existing files, just insert (clobbers; only for fast bootstrap)")
    sub_matched.add_argument('--default-link-rel',
        default="web",
        help="default URL rel for matches (eg, 'publisher', 'web')")

    sub_arabesque_match = subparsers.add_parser('arabesque',
        help="add file entities matched to releases from crawl log analysis")
    sub_arabesque_match.set_defaults(
        func=run_arabesque_match,
        auth_var="FATCAT_AUTH_WORKER_CRAWL",
    )
    sub_arabesque_match.add_argument('--sqlite-file',
        help="sqlite database file to import from")
    sub_arabesque_match.add_argument('--json-file',
        help="JSON file to import from (or stdin)",
        type=argparse.FileType('r'))
    sub_arabesque_match.add_argument('--do-updates',
        action='store_true',
        help="update pre-existing file entities if new match (instead of skipping)")
    sub_arabesque_match.add_argument('--no-require-grobid',
        action='store_true',
        help="whether postproc_status column must be '200'")
    sub_arabesque_match.add_argument('--extid-type',
        default="doi",
        help="identifer type in the database (eg, 'doi', 'pmcid'")
    sub_arabesque_match.add_argument('--crawl-id',
        help="crawl ID (optionally included in editgroup metadata)")
    sub_arabesque_match.add_argument('--default-link-rel',
        default="web",
        help="default URL rel for matches (eg, 'publisher', 'web')")

    sub_ingest_file = subparsers.add_parser('ingest-file-results',
        help="add/update flie entities linked to releases based on sandcrawler ingest results")
    sub_ingest_file.set_defaults(
        func=run_ingest_file,
        auth_var="FATCAT_AUTH_WORKER_CRAWL",
    )
    sub_ingest_file.add_argument('json_file',
        help="ingest_file JSON file to import from",
        default=sys.stdin, type=argparse.FileType('r'))
    sub_ingest_file.add_argument('--skip-source-whitelist',
        action='store_true',
        help="don't filter import based on request source whitelist")
    sub_ingest_file.add_argument('--kafka-mode',
        action='store_true',
        help="consume from kafka topic (not stdin)")
    sub_ingest_file.add_argument('--do-updates',
        action='store_true',
        help="update pre-existing file entities if new match (instead of skipping)")
    sub_ingest_file.add_argument('--no-require-grobid',
        action='store_true',
        help="whether postproc_status column must be '200'")
    sub_ingest_file.add_argument('--default-link-rel',
        default="web",
        help="default URL rel for matches (eg, 'publisher', 'web')")

    sub_savepapernow_file = subparsers.add_parser('savepapernow-file-results',
        help="add file entities crawled due to async Save Paper Now request")
    sub_savepapernow_file.set_defaults(
        func=run_savepapernow_file,
        auth_var="FATCAT_AUTH_WORKER_SAVEPAPERNOW",
    )
    sub_savepapernow_file.add_argument('json_file',
        help="ingest-file JSON file to import from",
        default=sys.stdin, type=argparse.FileType('r'))
    sub_savepapernow_file.add_argument('--kafka-mode',
        action='store_true',
        help="consume from kafka topic (not stdin)")

    sub_grobid_metadata = subparsers.add_parser('grobid-metadata',
        help="create release and file entities based on GROBID PDF metadata extraction")
    sub_grobid_metadata.set_defaults(
        func=run_grobid_metadata,
        auth_var="FATCAT_API_AUTH_TOKEN",
    )
    sub_grobid_metadata.add_argument('tsv_file',
        help="TSV file to import from (or stdin)",
        default=sys.stdin, type=argparse.FileType('r'))
    sub_grobid_metadata.add_argument('--group-size',
        help="editgroup group size to use",
        default=75, type=int)
    sub_grobid_metadata.add_argument('--longtail-oa',
        action='store_true',
        help="if this is an import of longtail OA content (sets an 'extra' flag)")
    sub_grobid_metadata.add_argument('--bezerk-mode',
        action='store_true',
        help="don't lookup existing files, just insert (clobbers; only for fast bootstrap)")

    sub_shadow_lib = subparsers.add_parser('shadow-lib',
        help="create release and file entities based on GROBID PDF metadata extraction")
    sub_shadow_lib.set_defaults(
        func=run_shadow_lib,
        auth_var="FATCAT_AUTH_WORKER_SHADOW",
    )
    sub_shadow_lib.add_argument('json_file',
        help="JSON file to import from (or stdin)",
        default=sys.stdin, type=argparse.FileType('r'))

    sub_wayback_static = subparsers.add_parser('wayback-static',
        help="crude crawl+ingest tool for single-page HTML docs from wayback")
    sub_wayback_static.set_defaults(
        func=run_wayback_static,
        auth_var="FATCAT_API_AUTH_TOKEN",
    )
    sub_wayback_static.add_argument('wayback_url',
        type=str,
        help="URL of wayback capture to extract from")
    sub_wayback_static.add_argument('--extid',
        type=str,
        help="external identifier for release lookup")
    sub_wayback_static.add_argument('--release-id',
        type=str,
        help="release entity identifier")
    sub_wayback_static.add_argument('--editgroup-id',
        type=str,
        help="use existing editgroup (instead of creating a new one)")

    sub_cdl_dash_dat = subparsers.add_parser('cdl-dash-dat',
        help="crude helper to import datasets from Dat/CDL mirror pilot project")
    sub_cdl_dash_dat.set_defaults(
        func=run_cdl_dash_dat,
        auth_var="FATCAT_API_AUTH_TOKEN",
    )
    sub_cdl_dash_dat.add_argument('dat_path',
        type=str,
        help="local path dat to import (must be the dat discovery key)")
    sub_cdl_dash_dat.add_argument('--release-id',
        type=str,
        help="release entity identifier")
    sub_cdl_dash_dat.add_argument('--editgroup-id',
        type=str,
        help="use existing editgroup (instead of creating a new one)")

    sub_datacite = subparsers.add_parser('datacite',
        help="import datacite.org metadata")
    sub_datacite.add_argument('json_file',
        help="File with jsonlines from datacite.org v2 API to import from",
        default=sys.stdin, type=argparse.FileType('r'))
    sub_datacite.add_argument('issn_map_file',
        help="ISSN to ISSN-L mapping file",
        default=None, type=argparse.FileType('r'))
    sub_datacite.add_argument('--extid-map-file',
        help="DOI-to-other-identifiers sqlite3 database",
        default=None, type=str)
    sub_datacite.add_argument('--kafka-mode',
        action='store_true',
        help="consume from kafka topic (not stdin)")
    sub_datacite.add_argument('--bezerk-mode',
        action='store_true',
        help="don't lookup existing DOIs, just insert (clobbers; only for fast bootstrap)")
    sub_datacite.add_argument('--debug',
        action='store_true',
        help="write converted JSON to stdout")
    sub_datacite.add_argument('--insert-log-file',
        default='',
        type=str,
        help="write inserted documents into file (for debugging)")
    sub_datacite.set_defaults(
        func=run_datacite,
        auth_var="FATCAT_AUTH_WORKER_DATACITE",
    )

    args = parser.parse_args()
    if not args.__dict__.get("func"):
        print("tell me what to do!")
        sys.exit(-1)

    # allow editgroup description override via env variable (but CLI arg takes
    # precedence)
    if not args.editgroup_description_override \
            and os.environ.get('FATCAT_EDITGROUP_DESCRIPTION'):
        args.editgroup_description_override = os.environ.get('FATCAT_EDITGROUP_DESCRIPTION')

    args.api = authenticated_api(
        args.host_url,
        # token is an optional kwarg (can be empty string, None, etc)
        token=os.environ.get(args.auth_var))
    args.func(args)

if __name__ == '__main__':
    main()
