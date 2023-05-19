def why_wrong_builder(card_id):
    card = Card.query.filter_by(id=card_id).first()
    ww_prompt = {
        "term": card.term,
        "subject": card.subject,
        "content": card.content,
        "boc_2": card.boc_2,
        "boc_3": card.boc_3,
        "boc_4": card.boc_4,
        "category": card.category,
        "card_id": card.id
    }
    return ww_prompt


@app.route("/send_question/<int:card_id>/", methods=['GET', 'POST'])
@login_required
def send_question(card_id):
    c_card_id = card_id
    logger.debug("send question")
    card = Card.query.filter_by(id=c_card_id).first()
    latest_paragraph = clean(request.form.get('latest_paragraph'))
    question = clean(request.form.get('question'))
    term = clean(card.term)
    content = clean(card.content)
    response = send_question_generator(term, content, latest_paragraph, question)
    json_response = {"response": response}
    return json_response   

@app.route("/news/", methods=['GET', 'POST'])
def news():
    return render_template('news.html')

@app.route("/public_cards/<int:deck_id>/", methods=['GET', 'POST'])
@login_required
def public_cards(deck_id):
    c_deck_id = deck_id
    deck = Deck.query.filter_by(id=c_deck_id).first()
    if deck.public == False:
        return apology("Sorry, this deck is not public")
    cards = (
            Card.query.filter(Card.decks_backref.any(id=deck_id))
            .order_by(Card.term.desc()).all()
    )
    return render_template('public_cards.html', cards=cards, deck=deck)


@app.route("/public_decks", methods = ['GET', 'POST'])
@login_required
def public_decks():
    form = SearchAndSortForm()
    decks = Deck.query.filter_by(public=True).all()
    search_query= form.search.data
    sort_method = form.sort.data
    # Start building the query
    query = Deck.query.filter(Deck.public == True)
    # Apply search filters if search_query is present
    if search_query:
        query = query.filter(
            or_(
                Deck.name.ilike(f'%{search_query}%'),
                Deck.description.ilike(f'%{search_query}%'),
                Deck.category.ilike(f'%{search_query}%')
            )
        )
    # Apply sorting if sort_method is not 'default'
    if sort_method != 'default':
        if sort_method == 'name_asc':
            query = query.order_by(Deck.name.asc())
        elif sort_method == 'name_desc':
            query = query.order_by(Deck.name.desc())
        elif sort_method == "category_asc":
            query = query.order_by(Deck.category.asc())
        elif sort_method == "category_desc":
            query = query.order_by(Deck.category.desc())

    # Execute the query and fetch all the decks
    decks = query.all()
    return render_template('public_decks.html', decks=decks, form = form)

@app.route("/deck_manager/<int:deck_id>", methods=['GET', 'POST'])
@login_required
def deck_manager(deck_id):
    share_form = Share()
    deck = Deck.query.filter_by(id=deck_id).first()
    tests = Test.query.filter_by(deck_id=deck_id).all()
    if current_user.id != deck.user_id:
        return apology("Sorry, this is not your deck")
    files = deck.deck_files
    return render_template('deck_manager.html', deck=deck, files=files,
                            share_form = share_form, tests = tests)


########################  STRIPE ###################################
##################################################################
################################
@app.route('/pricing', methods=['GET', 'POST'])
def pricing():
    return render_template('pricing.html')


@app.route('/upgrade', methods=['GET', 'POST'])
def upgrade():
    if not current_user.is_authenticated:
        flash('You must first have an account and be logged in'
            'before upgrading your account', 'warning')
        return redirect(url_for('index'))
    return render_template('upgrade.html')

counter = 0


@app.route("/stripe_webhook", methods=['POST'])
def stripe_webhook():
    logger.debug("entered webhook")
    valid_events = ['checkout.session.completed', 'invoice.paid', 
                    'invoice.payment_failed','invoice.payment_succeeded',
                    'customer.subscription.deleted', 'customer.subscription.updated',
                      'customer.subscription.created',
                    'customer.subscription.trial_will_end','customer.subscription.updated',
                      'customer.updated'
                    ]
    global counter
    counter += 1
    logger.debug(f"Webhook call #{counter}")
    payload = request.data.decode('utf-8')
    sig_header = request.headers.get('stripe-signature')
    event = None
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, endpoint_secret
        )
    except ValueError as e:
        # Invalid payload
        logger.exception("An exception occurred in stribe_webhook() route): %s", e)
        return 'Invalid payload', 401
    except stripe.error.SignatureVerificationError as e:
        # Invalid signature
        logger.debug(f"Signature verification error: {str(e)}")
        logger.error("An exception occurred in stribe_webhook() route): %s", e)

        return 'Invalid signature', 402
    # Handle the checkout.session.completed event
    if event['type'] in valid_events:
        # Fulfill the purchase...
        process_event_in_background(event)
    else:
        # Unknown event type
        logger.debug("unused event type %s", event['type'])
        return 'Unused event type', 200
    return 'Success', 200

def process_event_in_background(event):
    try:
        logger.debug('entered process_event_in_background')
        logger.debug("event type: %s", event['type'])
        stripe_event_id = event['id']
        event_type = event['type']
        event_data = json.dumps(event)
        created_at = datetime.utcnow()
        if event['type'] == 'checkout.session.completed':
            user_id = event['data']['object']['client_reference_id']
        else:
            user_id = None
        if event['type'] != 'customer.updated':
            stripe_customer_id = event['data']['object']['customer']
            logger.debug("CUSTOMER ID %s", event['data']['object']['customer'])
        else:
            stripe_customer_id = None
        stripe_event = StripeEvents(
            stripe_event_id=stripe_event_id,
            event_type=event_type,
            event_data=event_data,
            event_created=created_at,
            user_id=user_id,
            stripe_customer_id=stripe_customer_id,
        )
        db.session.add(stripe_event)
        db.session.commit()
    except Exception as e:
        logger.error("Exception in process_event_background function):%s", e)
        pass
    if event['type'] == 'checkout.session.completed':
        associate_stripe_customer_with_user(event)
        # Add a small delay to give the webhook function enough time to return a response
        time.sleep(1)
        # Store the event data in the StripeEvents table
        logger.debug("unused event type: %s", event['type'])
        stripe_event_id = event['id']
        event_type = event['type']
        event_data = json.dumps(event)
        created_at = datetime.utcnow()
        user_id = event['data']['object']['client_reference_id']
        stripe_customer_id = event['data']['object']['customer']
        logger.debug("CLIENT REF ID %s", event['data']['object']['client_reference_id'])
        logger.debug("CUSTOMER ID %s", event['data']['object']['customer'])
        stripe_event = StripeEvents(
            stripe_event_id=stripe_event_id,
            event_type=event_type,
            event_data=event_data,
            event_created=created_at,
            user_id=user_id,
            stripe_customer_id=stripe_customer_id,
        )
        db.session.add(stripe_event)
        db.session.commit()
        try:
            # Your event processing logic
            handle_checkout_session(event)
            # Update the event as processed in the StripeEvents table
            stripe_event.processed = True
            stripe_event.processed_at = datetime.utcnow()

        except Exception as e:
            # Update the StripeEvents table with the error message if processing fails
            stripe_event.error_message = str(e)
            current_app.logger.error('Exception in process_event_background'
                                    'function):%s', e)

        finally:
            db.session.commit()
    else:
        ## handle other event types
        pass

def associate_stripe_customer_with_user(event):
    try:
        idempo = str(uuid.uuid4())
        logger.debug("associating stripe customer with user")
        user_id = event['data']['object']['client_reference_id']
        stripe_customer_id = event['data']['object']['customer']
        ## modify user entry in DB
        user = User.query.filter_by(id=user_id).first()
        user.stripe_customer_id = stripe_customer_id
        ## modify stripe customer entry
        stripe.Customer.modify(
            stripe_customer_id,
            metadata={'user_id': user_id},
            idempotency_key=idempo, 
            )
        db.session.commit()
    except Exception as e:
        logger.debug("error associating stripe customer with user %s", e)
        raise

def handle_checkout_session(event):
    logger.debug('entered handle_checkout_session')
    plans_dict = {
    'price_1N8LZfGXWJkeH44yIj9OVi0N':'premium_yearly',
    'price_1N8LZ3GXWJkeH44yA1bxkLNY': 'premium_monthly', 
    'price_1N8LUuGXWJkeH44yZcPvdyIk': 'basic_yearly', 
    'price_1N8LSNGXWJkeH44yRgflWxVx': 'basic_monthly',
    }
    # Extract customer ID and subscription ID from the invoice object
    customer_id = event['data']['object']['customer']
    logger.debug("recognized customer id as %s", customer_id)
    ##subscription_id = event['data']['object']['subscription']
    checkout_session_id = event['data']['object']['id']
    line_items = stripe.checkout.Session.list_line_items(checkout_session_id)
    # Look up the user in your database using the customer ID
    user = User.query.filter_by(stripe_customer_id=customer_id).first()
    logger.debug('user is:  %s', user)
    if line_items.data:
        logger.debug("entered line_items.data")
        # Assuming there is only one line item
        item = line_items.data[0]
        product_id = item['price']['product']        
        price_id = item['price']['id']
        logger.debug(price_id)
        logger.debug("product_id %s",product_id)
        # Retrieve the product details from Stripe API
        product = stripe.Product.retrieve(product_id)
        product_name = product['name']
        logger.debug("product_name %s",product_name)
        plan = plans_dict[price_id]
        logger.debug(plan)
    try:
        if user:
            update_plan(user, plan)
    except Exception as e:
            ## log user not found error
            logger.debug("user not found")
            logger.error(f"Exception occurred in handle_checkout_session: {str(e)}") 
            raise e

def update_plan(user,plan):
    logger.debug('entered update_plan')
    try:
        if plan == 'basic_yearly':
            user.subscription_plan = 6
            user.subscription_start_date = datetime.utcnow()
            user.subscription_latest_roll_over = datetime.utcnow()
            set_usage_limit(user, 682700)
            
        elif plan == 'basic_monthly':
            user.subscription_plan = 4
            user.subscription_start_date = datetime.utcnow()
            user.subscription_latest_roll_over = datetime.utcnow()
            set_usage_limit(user, 682700)
        elif plan == 'premium_yearly':
            user.subscription_plan = 7
            user.subscription_start_date = datetime.utcnow()
            user.subscription_latest_roll_over = datetime.utcnow()
            set_usage_limit(user, 2048000)
        elif plan == 'premium_monthly':
            user.subscription_plan = 5
            user.subscription_start_date = datetime.utcnow()
            user.subscription_latest_roll_over = datetime.utcnow()
            set_usage_limit(user, 2048000)
        else:
            logger.debug("plan not found")
        logger.debug("%s, %s", user.id, user.subscription_plan)
        db.session.commit()
    except Exception as e:
        logger.debug(e)
        logger.debug("error updating plan")
        raise e

def set_usage_limit(user, n):
    new_record = UsageRecord(
        user_id=user.id,
        operation_type="Change plan",
        limit_count=n,
        operation_count=0,
        remaining_count=n,
        date=datetime.utcnow(),
        time_period = "month",
    )
    db.session.add(new_record)
    db.session.commit()
                        
####################### GROUPS #####################################################
####################################################################################
####################################################################################

@app.route('/my_groups')
@login_required
def my_groups():
    group_form = GroupForm()
    user_id = current_user.id
    created_groups = Group.query.filter_by(creator_id=user_id).all()
    user_groups = current_user.groups
    group_invites = get_invited_users_info(user_id)
    invitations = GroupInvite.query.filter_by(user_id=user_id).all()
    all_groups_member_roles = get_all_groups_member_roles(user_id)
    return render_template('my_groups.html', invitations = invitations,
                            groups=user_groups, created_groups = created_groups,
                            group_invites = group_invites,
                            user_roles = all_groups_member_roles,
                            form = group_form)

@app.route('/create_group', methods=['POST'])
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
        new_group.users.append(current_user)
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

@app.route("/invite_group/", methods=["GET", "POST"])
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
                not_users.append(email)
            elif already_invited is None:
                if user not in group.users:
                    new_invite = GroupInvite(name = group.name,
                        invited_by_email=current_user.email,
                        invited_by_id=current_user.id, user_id=user.id,
                        group_id=group_id, created_at = datetime.utcnow())
                    db.session.add(new_invite)
                    db.session.commit()
                if len(not_users) > 0:
                    flash('The following users are not registered:' + str(not_users),
                           'warning')
        return jsonify('success', 'User invited successfully')
    else:
        user = User.query.filter_by(email=user_email).first()
        if user is None:
            not_users.append(user_email)
        else:
            new_invite = GroupInvite(name = group.name,
                        invited_by_email=current_user.email,
                        invited_by_id=current_user.id, user_id=user.id,
                        group_id=group_id, created_at = datetime.utcnow())
            db.session.add(new_invite)
            db.session.commit()
        if len(not_users) > 0:
            flash('The following users are not registered: ' + str(not_users), 'warning')
        return jsonify('success', 'User invited successfully')


@app.route("/approve_group/<int:group_id>/", methods=["GET", "POST"])
@login_required
def approve_group(group_id):
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
    
@app.route("/reject_group/<int:group_id>/", methods=["GET", "POST"])
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
    # Get the user IDs from the invite_group table for those groups
    invited_users = (
            db.session.query(User.id, User.username, User.email)
            .join(GroupInvite, GroupInvite.user_id == User.id)
            .filter(GroupInvite.group_id.in_(user_groups)).all()
    )
    return invited_users

@app.route("/group/<int:group_id>/", methods=["GET", "POST"])
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
    return render_template('group.html', mydecks = mydecks,
                group=group, group_member_roles=group_member_roles,
                invited_users=invited_users, decks = decks, permissions = permissions)

@app.route('/group/<int:group_id>/update_member_permissions', methods=['POST'])
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

@app.route('/search_public_decks', methods=['POST'])
@login_required
def search_public_decks():
    data = request.json
    search_term = clean(data['search'])
    decks = Deck.query.filter(Deck.public == True, Deck.name.contains(search_term)).all()
    return jsonify([deck.serialize() for deck in decks])

@app.route('/add_deck_to_group', methods=['POST'])
@login_required
def add_deck_to_group():
    data = request.json
    group_id = clean(data['group_id'])
    if check_group_write_permission(group_id) == False:
        return jsonify({"status": "error",
                    "message": "You do not have permission to add decks to this group"})
    else:
        deck_id = data['deck_id']
        group = Group.query.get(group_id)
        existing_deck = Deck.query.get(deck_id)
        new_deck = Deck(user_id = current_user.id,
                name=existing_deck.name, description=existing_deck.description,
                group_id = group_id, time_created=datetime.utcnow())
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
            new_deck.cards.append(new_card)
        db.session.commit()
        return jsonify({"status": "success"})

def check_group_write_permission(group_id):
    c_group_id = group_id
    user_id = current_user.id
    association = db.session.query(user_group_association).filter_by(user_id=user_id,
                                                                      group_id=c_group_id).first()
    if association and association.permissions and 'write' in association.permissions:
        return True
    else:
        logger.debug("no permission to edit")
        return False

@app.route("/delete_group/<int:group_id>/", methods=["GET", "POST"])
@login_required
def delete_group(group_id):
    c_group_id = group_id
    group = Group.query.get(c_group_id)
    if group.creator_id == current_user.id:
        GroupInvite.query.filter_by(group_id=c_group_id).delete()
        db.session.delete(group)
        db.session.commit()
        return redirect(url_for('my_groups'))
    else:
        return jsonify({"message": "You do not have permission to delete this group",
                         "status": "error"})


@app.route("/import_from_group/<int:deck_id>/<int:group_id>", methods=["GET", "POST"])
@login_required
def import_from_group(deck_id, group_id):
    c_group_id = group_id
    c_deck_id = deck_id
    group = Group.query.get(c_group_id)
    existing_deck = Deck.query.get(c_deck_id)
    group = Group.query.filter_by(id=c_group_id).first()
    user_ids = [user.id for user in group.users]
    if current_user.id in user_ids:
        new_deck = Deck(user_id = current_user.id,
                name=existing_deck.name, description=existing_deck.description,
                group_id = group_id, time_created=datetime.utcnow())
        for card in existing_deck.cards:
            new_card = Card(term=card.term, content=card.content,
                boc_2=card.boc_2, boc_3=card.boc_3, boc_4=card.boc_4, img=card.img,
                sound=card.sound, subject=card.subject, topic=card.topic,
                category=card.category, prompt_option=card.prompt_option,
                prompt_option2=card.prompt_option2, trans_option=card.trans_option,
                len_option=card.len_option, qmin_option=card.qmin_option,
                qmax_option=card.qmax_option, diff_lvl=card.diff_lvl)
            new_deck.cards.append(new_card)
        db.session.add(new_deck)
        return jsonify({"message": "Deck imported successfully", "status": "success"})
    else:
        return jsonify({"message":"You don't have permission to import from this group",
                         "status": "error"})

@app.route("/remove_user_group/<int:group_id>/<int:user_id>", methods=["GET", "POST"])
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
###################### TO BE REORGANIZED ###############################################

def split_string(string):
    items = string.split("&-&-&")
    return items
################## CURRENTLY UNUSED ####################################################


if __name__ == "__main__":
    app.run(debug=DEBUG)
else:
    # For Alembic
    from models import db
    db.init_app(app)