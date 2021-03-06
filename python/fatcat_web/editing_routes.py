
import os
import json
from flask import Flask, render_template, send_from_directory, request, \
    url_for, abort, g, redirect, jsonify, session, flash, Response
from flask_login import login_required

from fatcat_openapi_client import Editgroup
from fatcat_openapi_client.rest import ApiException
from fatcat_tools.transforms import *
from fatcat_web import app, api, auth_api, priv_api
from fatcat_web.auth import handle_token_login, handle_logout, load_user, handle_ia_xauth
from fatcat_web.cors import crossdomain
from fatcat_web.search import *
from fatcat_web.forms import *
from fatcat_web.entity_helpers import *


### Helper Methods ##########################################################

def form_editgroup_get_or_create(api, edit_form):
    """
    This function expects a submitted, validated 
    """
    if edit_form.editgroup_id.data:
        try:
            eg = api.get_editgroup(edit_form.editgroup_id.data)
        except ApiException as ae:
            if ae.status == 404:
                edit_form.editgroup_id.errors.append("Editgroup does not exist")
                return None
            app.log.warning(ae)
            abort(ae.status)
        if eg.changelog_index:
            edit_form.editgroup_id.errors.append("Editgroup has already been accepted")
            return None
    else:
        # if no editgroup, create one from description
        try:
            eg = api.create_editgroup(
                Editgroup(description=edit_form.editgroup_description.data or None))
        except ApiException as ae:
            app.log.warning(ae)
            abort(ae.status)
        # set this session editgroup_id
        flash('Started new editgroup <a href="/editgroup/{}">{}</a>' \
            .format(eg.editgroup_id, eg.editgroup_id))
    return eg

def generic_entity_edit(editgroup_id, entity_type, existing_ident, edit_template):
    """

    existing (entity)

    Create: existing blank, ident blank, editgroup optional
    Update: ident set

    Need to handle:
    - editgroup not set (need to create one)
    - creating entity from form
    - updating an existing ident
    - updating an existing editgroup/ident

    Views:
    - /container/create
    - /container/<ident>/edit
    - /editgroup/<editgroup_id>/container/<ident>/edit

    Helpers:
    - get_editgroup_revision(editgroup, entity_type, ident) -> None or entity
    
    TODO: prev_rev interlock
    """

    # fetch editgroup (if set) or 404
    editgroup = None
    if editgroup_id:
        try:
            editgroup = api.get_editgroup(editgroup_id)
        except ApiException as ae:
            abort(ae.status)

        # check that editgroup is edit-able
        if editgroup.changelog_index != None:
            flash("Editgroup already merged")
            abort(400)

    # fetch entity (if set) or 404
    existing = None
    existing_edit = None
    if editgroup and existing_ident:
        existing, existing_edit = generic_get_editgroup_entity(editgroup, entity_type, existing_ident)
    elif existing_ident:
        existing = generic_get_entity(entity_type, existing_ident)

    # parse form (if submitted)
    status = 200
    if entity_type == 'container':
        form = ContainerEntityForm()
    elif entity_type == 'file':
        form = FileEntityForm()
    elif entity_type == 'release':
        form = ReleaseEntityForm()
    else:
        raise NotImplementedError

    if form.is_submitted():
        if form.validate_on_submit():
            # API on behalf of user
            user_api = auth_api(session['api_token'])
            if not editgroup:
                editgroup = form_editgroup_get_or_create(user_api, form)

            if editgroup:

                if not existing_ident: # it's a create
                    entity = form.to_entity()
                    try:
                        if entity_type == 'container':
                            edit = user_api.create_container(editgroup.editgroup_id, entity)
                        elif entity_type == 'file':
                            edit = user_api.create_file(editgroup.editgroup_id, entity)
                        elif entity_type == 'release':
                            edit = user_api.create_release(editgroup.editgroup_id, entity)
                        else:
                            raise NotImplementedError
                    except ApiException as ae:
                        app.log.warning(ae)
                        abort(ae.status)
                    return redirect('/editgroup/{}/{}/{}'.format(editgroup.editgroup_id, entity_type, edit.ident))
                else: # it's an update
                    # all the tricky logic is in the update method
                    form.update_entity(existing)
                    # do we need to try to delete the current in-progress edit first?
                    # TODO: some danger of wiping database state here is
                    # "updated edit" causes, eg, a 4xx error. Better to allow
                    # this in the API itself. For now, form validation *should*
                    # catch most errors, and if not editor can hit back and try
                    # again. This means, need to allow failure of deletion.
                    if existing_edit:
                        # need to clear revision on object or this becomes just
                        # a "update pointer" edit
                        existing.revision = None
                        try:
                            if entity_type == 'container':
                                user_api.delete_container_edit(editgroup.editgroup_id, existing_edit.edit_id)
                            elif entity_type == 'file':
                                user_api.delete_file_edit(editgroup.editgroup_id, existing_edit.edit_id)
                            elif entity_type == 'release':
                                user_api.delete_release_edit(editgroup.editgroup_id, existing_edit.edit_id)
                            else:
                                raise NotImplementedError
                        except ApiException as ae:
                            if ae.status == 404:
                                pass
                            else:
                                abort(ae.status)
                    try:
                        if entity_type == 'container':
                            edit = user_api.update_container(editgroup.editgroup_id, existing.ident, existing)
                        elif entity_type == 'file':
                            edit = user_api.update_file(editgroup.editgroup_id, existing.ident, existing)
                        elif entity_type == 'release':
                            edit = user_api.update_release(editgroup.editgroup_id, existing.ident, existing)
                        else:
                            raise NotImplementedError
                    except ApiException as ae:
                        app.log.warning(ae)
                        abort(ae.status)
                    return redirect('/editgroup/{}/{}/{}'.format(editgroup.editgroup_id, entity_type, edit.ident))
            else:
                status = 400
        elif form.errors:
            status = 400
            app.log.info("form errors (did not validate): {}".format(form.errors))

    else: # form is not submitted
        if existing:
            if entity_type == 'container':
                form = ContainerEntityForm.from_entity(existing)
            elif entity_type == 'file':
                form = FileEntityForm.from_entity(existing)
            elif entity_type == 'release':
                form = ReleaseEntityForm.from_entity(existing)
            else:
                raise NotImplementedError

    editor_editgroups = api.get_editor_editgroups(session['editor']['editor_id'], limit=20)
    potential_editgroups = [e for e in editor_editgroups if e.changelog_index == None and e.submitted == None]

    if not form.is_submitted():
        # default to most recent not submitted, fallback to "create new"
        form.editgroup_id.data = ""
        if potential_editgroups:
            form.editgroup_id.data = potential_editgroups[0].editgroup_id

    return render_template(edit_template, form=form,
        existing_ident=existing_ident, editgroup=editgroup,
        potential_editgroups=potential_editgroups), status

def generic_edit_delete(editgroup_id, entity_type, edit_id):
    # fetch editgroup (if set) or 404
    editgroup = None
    if editgroup_id:
        try:
            editgroup = api.get_editgroup(editgroup_id)
        except ApiException as ae:
            abort(ae.status)

        # check that editgroup is edit-able
        if editgroup.changelog_index != None:
            flash("Editgroup already merged")
            abort(400)

    # API on behalf of user
    user_api = auth_api(session['api_token'])
    
    # do the deletion
    try:
        if entity_type == 'container':
            user_api.delete_container_edit(editgroup.editgroup_id, edit_id)
        elif entity_type == 'file':
            user_api.delete_file_edit(editgroup.editgroup_id, edit_id)
        elif entity_type == 'release':
            user_api.delete_release_edit(editgroup.editgroup_id, edit_id)
        else:
            raise NotImplementedError
    except ApiException as ae:
        abort(ae.status)
    return redirect("/editgroup/{}".format(editgroup_id))


### Views ###################################################################

@app.route('/container/create', methods=['GET', 'POST'])
@login_required
def container_create_view():
    return generic_entity_edit(None, 'container', None, 'container_create.html')

@app.route('/container/<ident>/edit', methods=['GET', 'POST'])
@login_required
def container_edit(ident):
    return generic_entity_edit(None, 'container', ident, 'container_edit.html')

@app.route('/editgroup/<editgroup_id>/container/<ident>/edit', methods=['GET', 'POST'])
@login_required
def container_editgroup_edit(editgroup_id, ident):
    return generic_entity_edit(editgroup_id, 'container', ident, 'container_edit.html')

@app.route('/editgroup/<editgroup_id>/container/edit/<edit_id>/delete', methods=['POST'])
@login_required
def container_edit_delete(editgroup_id, edit_id):
    return generic_edit_delete(editgroup_id, 'container', edit_id)

@app.route('/file/create', methods=['GET', 'POST'])
@login_required
def file_create_view():
    return generic_entity_edit(None, 'file', None, 'file_create.html')

@app.route('/file/<ident>/edit', methods=['GET', 'POST'])
@login_required
def file_edit(ident):
    return generic_entity_edit(None, 'file', ident, 'file_edit.html')

@app.route('/editgroup/<editgroup_id>/file/<ident>/edit', methods=['GET', 'POST'])
@login_required
def file_editgroup_edit(editgroup_id, ident):
    return generic_entity_edit(editgroup_id, 'file', ident, 'file_edit.html')

@app.route('/editgroup/<editgroup_id>/file/edit/<edit_id>/delete', methods=['POST'])
@login_required
def file_edit_delete(editgroup_id, edit_id):
    return generic_edit_delete(editgroup_id, 'file', edit_id)

@app.route('/release/create', methods=['GET', 'POST'])
@login_required
def release_create_view():
    return generic_entity_edit(None, 'release', None, 'release_create.html')

@app.route('/release/<ident>/edit', methods=['GET', 'POST'])
@login_required
def release_edit(ident):
    return generic_entity_edit(None, 'release', ident, 'release_edit.html')

@app.route('/editgroup/<editgroup_id>/release/<ident>/edit', methods=['GET', 'POST'])
@login_required
def release_editgroup_edit(editgroup_id, ident):
    return generic_entity_edit(editgroup_id, 'release', ident, 'release_edit.html')

@app.route('/editgroup/<editgroup_id>/release/edit/<edit_id>/delete', methods=['POST'])
@login_required
def release_edit_delete(editgroup_id, edit_id):
    return generic_edit_delete(editgroup_id, 'release', edit_id)


### Not-Implemented Views ###################################################

@app.route('/creator/create', methods=['GET'])
def creator_create_view():
    return abort(404)

@app.route('/creator/<ident>/edit', methods=['GET'])
def creator_edit(ident):
    return render_template('entity_edit.html'), 404

@app.route('/editgroup/<editgroup_id>/creator/<ident>/edit', methods=['GET', 'POST'])
def creator_editgroup_edit(editgroup_id, ident):
    return abort(404)

@app.route('/editgroup/<editgroup_id>/creator/edit/<edit_id>/delete', methods=['POST'])
def creator_edit_delete(editgroup_id, edit_id):
    return abort(404)

@app.route('/fileset/create', methods=['GET'])
def fileset_create_view():
    return abort(404)

@app.route('/fileset/<ident>/edit', methods=['GET'])
def fileset_edit(ident):
    return render_template('entity_edit.html'), 404

@app.route('/editgroup/<editgroup_id>/fileset/<ident>/edit', methods=['GET', 'POST'])
def fileset_editgroup_edit(editgroup_id, ident):
    return abort(404)

@app.route('/editgroup/<editgroup_id>/fileset/edit/<edit_id>/delete', methods=['POST'])
def fileset_edit_delete(editgroup_id, edit_id):
    return abort(404)

@app.route('/webcapture/create', methods=['GET'])
def webcapture_create_view():
    return abort(404)

@app.route('/webcapture/<ident>/edit', methods=['GET'])
def webcapture_edit(ident):
    return render_template('entity_edit.html'), 404

@app.route('/editgroup/<editgroup_id>/webcapture/<ident>/edit', methods=['GET', 'POST'])
def webcapture_editgroup_edit(editgroup_id, ident):
    return abort(404)

@app.route('/editgroup/<editgroup_id>/webcapture/edit/<edit_id>/delete', methods=['POST'])
def webcapture_edit_delete(editgroup_id, edit_id):
    return abort(404)

@app.route('/work/create', methods=['GET'])
def work_create_view():
    return abort(404)

@app.route('/work/<ident>/edit', methods=['GET'])
def work_edit(ident):
    return render_template('entity_edit.html'), 404

@app.route('/editgroup/<editgroup_id>/work/<ident>/edit', methods=['GET', 'POST'])
def work_editgroup_edit(editgroup_id, ident):
    return abort(404)

@app.route('/editgroup/<editgroup_id>/work/edit/<edit_id>/delete', methods=['POST'])
def work_edit_delete(editgroup_id, edit_id):
    return abort(404)

