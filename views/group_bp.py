
import logging
import datetime as dt
from urllib.parse import unquote
from flask import Blueprint, render_template, flash, redirect, request, url_for, jsonify
from flask_login import login_required, current_user
from sqlalchemy.sql import and_
from bleach import clean
from models.creators.formatters import check_comma_list
from models.models_ import Card, Deck, GroupInvite, Group, User, user_group_association
from models.forms.forms import GroupForm
from run.extensions import db


logger = logging.getLogger("flask_app")
group_bp = Blueprint(
    'group_bp', 
    __name__,
    template_folder='templates/group_bp',
    static_folder='static'
)

@group_bp.route('/remove_deck_from_group/<group_id>/<deck_id>', methods=['GET','POST'])
@login_required
def remove_deck_from_group(group_id, deck_id):
    logger.debug("remove deck from group")
    group = Group.query.filter_by(id=group_id).first()
    deck = Deck.query.filter_by(id=deck_id).first()
    group.decks.remove(deck)
    db.session.commit()
    return redirect(("/group_bp/group/{group}").format(group=group.id)) 


@group_bp.route('/my_groups')
@login_required
def my_groups():
    group_form = GroupForm()
    user_id = current_user.id
    created_groups = Group.query.filter_by(creator_id=user_id).all()
    user_groups = current_user.groups
    group_invites = get_invited_users_info(user_id)
    invitations = GroupInvite.query.filter_by(user_id=user_id).all()
    all_groups_member_roles = get_all_groups_member_roles(user_id)
    return render_template('/group_bp/my_groups.html', invitations = invitations,
                            groups=user_groups, created_groups = created_groups,
                            group_invites = group_invites,
                            user_roles = all_groups_member_roles,
                            form = group_form)

@group_bp.route('/create_group', methods=['POST'])
@login_required
def create_group():
    logger.debug("create group")
    form = GroupForm(request.form)
    if form.validate():
        logger.debug("form validated")
        name = form.name.data
        description = form.description.data
        group_type = form.group_type.data
        private = form.is_private.data
        user_id = current_user.id
        new_group = Group(name=name, description=description,
                        group_type=group_type, is_private=private, creator_id=user_id)
        db.session.add(new_group)
        new_group.users.group_bpend(current_user)
        db.session.commit()
        update_member_permissions(new_group.id, user_id, "write")
        logger.debug("where")
        db.session.commit()
        success_response = jsonify({'message': 'Group created successfully'}), 201
        
        logger.debug("Success response: %s", success_response)# Log the success response
        return success_response
    else:
        logger.debug("form not validated")
        logger.debug("Form errors: %s", form.errors)  # Log the form errors
        errors = form.errors
        return jsonify(errors), 400

@group_bp.route("/invite_group/", methods=["GET", "POST"])
@login_required
def invite_group():
    group_id = request.args.get('groupId', type=int)
    user_email = request.args.get('email', type=str)
    not_users = []
    group = Group.query.filter_by(id=group_id).first()
    if check_comma_list(user_email):
        users_emails = user_email.split(",")
        for email in users_emails:
            logger.debug("user email %s", email)
            email = unquote(email).strip()
            user = User.query.filter_by(email=email).first()
            already_invited = GroupInvite().query.filter_by(user_id=user.id,
                                                            group_id=group_id).first()
            if user is None:
                not_users.group_bpend(email)
            elif already_invited is None:
                if user not in group.users:
                    new_invite = GroupInvite(name = group.name,
                        invited_by_email=current_user.email,
                        invited_by_id=current_user.id, user_id=user.id,
                        group_id=group_id, created_at = dt.datetime.now(dt.timezone.utc))
                    db.session.add(new_invite)
                    db.session.commit()
                if len(not_users) > 0:
                    flash('The following users are not registered:' + str(not_users),
                           'warning')
        return jsonify('success', 'User invited successfully')
    else:
        user = User.query.filter_by(email=user_email).first()
        if user is None:
            not_users.group_bpend(user_email)
        else:
            new_invite = GroupInvite(name = group.name,
                        invited_by_email=current_user.email,
                        invited_by_id=current_user.id, user_id=user.id,
                        group_id=group_id, created_at = dt.datetime.now(dt.timezone.utc))
            db.session.add(new_invite)
            db.session.commit()
        if len(not_users) > 0:
            flash('The following users are not registered: ' + str(not_users), 'warning')
        return jsonify('success', 'User invited successfully')


@group_bp.route("/group_bprove_group/<int:group_id>/", methods=["GET", "POST"])
@login_required
def group_bprove_group(group_id):
    c_group_id = group_id
    group_invite = GroupInvite.query.filter_by(id=c_group_id,
                                            user_id=current_user.id).first()
    if group_invite:
        group = Group.query.get_or_404(group_invite.group_id)
        db.session.execute(user_group_association.insert().values(
            user_id=current_user.id, 
            group_id=group.id, 
            role="member", 
            permissions="read",
            ))
        db.session.delete(group_invite)
        db.session.commit()
        return jsonify('success', 'User added to group successfully')
    
@group_bp.route("/reject_group/<int:group_id>/", methods=["GET", "POST"])
@login_required
def reject_group(group_id):
    c_group_id = group_id
    group_invite = GroupInvite.query.filter_by(id=c_group_id,
                                            user_id=current_user.id).first()
    if group_invite:
        db.session.delete(group_invite)
        db.session.commit()
        return jsonify('success', 'User rejected successfully')
    else:
        return jsonify('error', 'User not invited to group')

def get_group_member_roles(group_id):
    c_group_id = group_id
    results = db.session.query(User.id, User.username,
                        User.email,
                        user_group_association.c.role).join(user_group_association).filter(
        user_group_association.c.group_id == c_group_id
    ).all()
    group_member_roles = {}
    for result in results:
        if result.username is not None:
            username_or_email = result.username
        else:
            username_or_email = result.email
        group_member_roles[result.id] = {
            'username': username_or_email,
            'role': result.role
        }
    return group_member_roles

def get_all_groups_member_roles(user_id):
    c_user_id = user_id
    user_groups = db.session.query(Group).join(user_group_association).filter(
        user_group_association.c.user_id == c_user_id
    ).all()
    all_groups_member_roles = {}
    for group in user_groups:
        group_member_roles = get_group_member_roles(group.id)
        all_groups_member_roles[group.id] = group_member_roles
    return all_groups_member_roles

def get_group_member_permissions(group_id):
    c_group_id = group_id
    results = db.session.query(User.id,
                    User.username, User.email,
                    user_group_association.c.permissions).join(user_group_association).filter(
        user_group_association.c.group_id == c_group_id
    ).all()
    group_member_permissions = {}
    for result in results:
        if result.username is not None:
            username_or_email = result.username
        else:
            username_or_email = result.email
        group_member_permissions[result.id] = {
            'username': username_or_email,
            'permissions': result.permissions
        }
    return group_member_permissions

def get_all_groups_member_permissions(user_id):
    c_user_id = user_id
    user_groups = db.session.query(Group).join(user_group_association).filter(
        user_group_association.c.user_id == c_user_id
    ).all()
    all_groups_member_permissions = {}
    for group in user_groups:
        group_member_permissions = get_group_member_permissions(group.id)
        all_groups_member_permissions[group.id] = group_member_permissions
    return all_groups_member_permissions

def get_invited_users_info(user_id):
    c_user_id = user_id
    # Get all the groups the user is a part of
    user_groups_query = db.session.query(Group.id).join(user_group_association).filter(
        user_group_association.c.user_id == c_user_id
    ).all()
    # Extract the group IDs from the Row objects
    user_groups = [row[0] for row in user_groups_query]
    return (
        db.session.query(User.id, User.username, User.email)
        .join(GroupInvite, GroupInvite.user_id == User.id)
        .filter(GroupInvite.group_id.in_(user_groups))
        .all()
    )

@group_bp.route("/group/<int:group_id>/", methods=["GET", "POST"])
@login_required
def group(group_id):
    c_group_id = group_id
    mydecks = Deck.query.filter_by(user_id = current_user.id).all()
    group = Group.query.get_or_404(c_group_id)
    ## get group members and their roles
    group_member_roles = get_group_member_roles(c_group_id)
    ## get invited group members
    invited_users = get_invited_users_info(current_user.id)
    decks = Deck.query.filter_by(group_id=c_group_id).all()
    permissions = get_group_member_permissions(group_id)
    return render_template('/group_bp/group.html', mydecks = mydecks,
                group=group, group_member_roles=group_member_roles,
                invited_users=invited_users, decks = decks, permissions = permissions)

@group_bp.route('/group/<int:group_id>/update_member_permissions', methods=['POST'])
@login_required
def update_member_permissions(group_id, user_id = None, permission = None):
    logger.debug("entered member permissions update")
    c_group_id = group_id
    if user_id:
        logger.debug("user id is %s", user_id)
        target_user_id = user_id
    else:
        data = request.json
        target_user_id = int(data['target_user_id'])
    if permission:
        logger.debug("permission is %s", permission)
        new_permissions = permission
    else:
        new_permissions = data['new_permissions']
    # Check if the current user is the creator of the group
    group = Group.query.get(c_group_id)
    logger.debug("group is %s", group)
    user_id = current_user.id
    if group.creator_id == user_id:
        # Update the target user's permissions
        db.session.query(user_group_association).filter(
            user_group_association.c.group_id == c_group_id,
            user_group_association.c.user_id == target_user_id
        ).update({user_group_association.c.permissions: new_permissions})
        db.session.commit()
        response = {
            "status": "success",
            "message": "Member permissions updated successfully"
        }
    else:
        response = {
            "status": "error",
            "message": "You do not have permission to update member permissions"
        }
    logger.debug(response)
    return jsonify(response)

@group_bp.route('/search_public_decks', methods=['POST'])
@login_required
def search_public_decks():
    data = request.json
    search_term = clean(data['search'])
    decks = Deck.query.filter(Deck.public is True, Deck.name.contains(search_term)).all()
    return jsonify([deck.serialize() for deck in decks])

@group_bp.route('/add_deck_to_group', methods=['POST'])
@login_required
def add_deck_to_group():
    data = request.json
    group_id = clean(data['group_id'])
    if check_group_write_permission(group_id) is False:
        return jsonify({"status": "error",
                    "message": "You do not have permission to add decks to this group"})
    
    deck_id = data['deck_id']
    group = Group.query.get(group_id)
    existing_deck = Deck.query.get(deck_id)
    new_deck = Deck(user_id = current_user.id,
            name=existing_deck.name, description=existing_deck.description,
            group_id = group_id, time_created=dt.datetime.now(dt.timezone.utc))
    db.session.add(new_deck)
    for card in existing_deck.cards:
        new_card = Card(term=card.term,
            content=card.content, boc_2=card.boc_2, boc_3=card.boc_3,
            boc_4=card.boc_4, img=card.img, sound=card.sound,
            subject=card.subject, topic=card.topic, category=card.category,
            prompt_option=card.prompt_option, prompt_option2=card.prompt_option2,
            trans_option=card.trans_option, len_option=card.len_option,
            qmin_option=card.qmin_option, qmax_option=card.qmax_option,
            diff_lvl=card.diff_lvl)
        new_deck.cards.group_bpend(new_card)
    db.session.commit()
    return jsonify({"status": "success"})

def check_group_write_permission(group_id):
    c_group_id = group_id
    user_id = current_user.id
    association = db.session.query(user_group_association).filter_by(user_id=user_id,
                                                                      group_id=c_group_id).first()
    if association and association.permissions and 'write' in association.permissions:
        return True
    logger.debug("no permission to edit")
    return False

@group_bp.route("/delete_group/<int:group_id>/", methods=["GET", "POST"])
@login_required
def delete_group(group_id):
    c_group_id = group_id
    group = Group.query.get(c_group_id)
    if group.creator_id == current_user.id:
        GroupInvite.query.filter_by(group_id=c_group_id).delete()
        db.session.delete(group)
        db.session.commit()
        return redirect(url_for('group_bp.my_groups'))
    else:
        return jsonify({"message": "You do not have permission to delete this group",
                         "status": "error"})


@group_bp.route("/import_from_group/<int:deck_id>/<int:group_id>", methods=["GET", "POST"])
@login_required
def import_from_group(deck_id, group_id):
    c_group_id = group_id
    c_deck_id = deck_id
    group = Group.query.get(c_group_id)
    existing_deck = Deck.query.get(c_deck_id)
    group = Group.query.filter_by(id=c_group_id).first()
    user_ids = [user.id for user in group.users]
    if current_user.id not in user_ids:
        return jsonify({"message":"You don't have permission to import from this group",
                         "status": "error"})
    new_deck = Deck(user_id = current_user.id,
            name=existing_deck.name, description=existing_deck.description,
            group_id = group_id, time_created=dt.datetime.now(dt.timezone.utc))
    for card in existing_deck.cards:
        new_card = Card(term=card.term, content=card.content,
            boc_2=card.boc_2, boc_3=card.boc_3, boc_4=card.boc_4, img=card.img,
            sound=card.sound, subject=card.subject, topic=card.topic,
            category=card.category, prompt_option=card.prompt_option,
            prompt_option2=card.prompt_option2, trans_option=card.trans_option,
            len_option=card.len_option, qmin_option=card.qmin_option,
            qmax_option=card.qmax_option, diff_lvl=card.diff_lvl)
        new_deck.cards.group_bpend(new_card)
    db.session.add(new_deck)
    return jsonify({"message": "Deck imported successfully", "status": "success"})

@group_bp.route("/remove_user_group/<int:group_id>/<int:user_id>", methods=["GET", "POST"])
@login_required
def remove_user_group(group_id, user_id):
    logger.debug("remove user group")
    c_group_id = group_id
    c_user_id = user_id
    group = Group.query.get(c_group_id)
    if group.creator_id == current_user.id:
        association = db.session.query(user_group_association).filter(
            and_(user_group_association.c.user_id == c_user_id,
                user_group_association.c.group_id == c_group_id)
        ).first()
        if association:
            db.session.execute(
                user_group_association.delete().where(
                    and_(user_group_association.c.user_id == c_user_id,
                        user_group_association.c.group_id == c_group_id)
                )
            )
            db.session.commit()
        return jsonify({"message": "User removed successfully", "status": "success"})
    else:
        return jsonify({"message": "You do not have permission"
                    "to remove users from this group", "status": "error"})
    