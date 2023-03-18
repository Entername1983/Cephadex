@app.route("/extract", methods = ["GET", "POST"])
@login_required
def extract():
    form = UploadFileForm()
    mapping = {
    "Definitions": ("A", "B"),
    "Translate": ("A", "B"),
    "Rhyme": ("A", "B"),
    "People": ("A", "B"),
    "Theories": ("A", "B"),
    "Cloze": ("A", "B"),
    "Mcq": ("A", "B", "C", "D", "E"),
    "Comprehension": ("A", "B"),
    "Vocab_builder": ("A", "B"),
    "Formulas": ("A", "B", "C"),
    }
    ## main prompt option
    ## subject
    prompt_option2 = None
    lang_option = None
    trans_option = None
    ## detail level
    len_option = None
    qmin_option = None
    qmax_option = None
    ## custom 
    
    if form.validate_on_submit():
        ## load type of card to be made to prompt_option
        if form.prompt.data != None:       
            prompt_option = form.prompt.data
            print(prompt_option)
        ## load translate option  
        if form.languages.data != None:    
            trans_option = form.languages.data
        ## load secondary prompt option
        if form.subject.data:
            prompt_option2 = form.subject.data
        ## load language output option (defaults to English)
        if form.main_lang.data:
            lang_option = form.main_lang.data
        if form.length.data:
            len_option = form.length.data
        if form.qmin_option.data:
            qmin_option = form.qmin_option.data
        if form.qmax_option.data:
            qmax_option = form.qmax_option.data
                
        ## use existing deck or create a new one
        if form.deck_list.data != None:
            deck = form.deck_list.data
        else:
            deck_name = form.name.data
            if form.description.data != None:
                deck_description = form.description.data
            else:
                deck_description = " ".join(prompt_option + "deck")
            deck = Deck(name=deck_name, description=deck_description)
            db.session.add(deck) 
        ## GET TEXT FROM INPUT 
        if form.file.data != None:
            f_type = form.file.data.content_type  
            method = "file upload"
            file = form.file.data
            file_loc = (os.path.join(os.path.abspath(os.path.dirname(__file__)),app.config['UPLOAD_FOLDER'],secure_filename(file.filename)))
            file.save(file_loc)
            text = text_extractor(file_loc)
        elif form.text_input.data is not None and form.text_input.data.strip() != '':
            f_type = "text"
            method = "text input"
            text = form.text_input.data  
        elif form.link_input.data != None and form.link_input.data.strip() != '':
            f_type = "link"
            method = "link input"
            text = None
            link_input = form.link_input.data
            if "wikipedia" in form.link_input.data:
                if check_comma_list(link_input):
                    link_input = link_input.split(",")
                    for link in link_input:
                        part = extract_from_wiki(link_input)
                    if text == None:
                        text = part
                    text = text + part
                text = extract_from_wiki(link_input)   
                    
            else:
                if check_comma_list(link_input):
                    link_input = link_input.split(",")
                    for link in link_input:
                        link = get_video_id(link)
                        part = extract_from_youtube(link)
                        if text == None:
                            text = part
                        text = text + part
                link_input = get_video_id(link_input)
                text = extract_from_youtube(link_input)
         ## RETURN OUTPUT
        tokens = count_tokens(text)
        operation_details = prompt_option  
        if perform_operation(current_user, operation_details, tokens) == False:
            flash('You have reached your monthly usage limit.  Please upgrade your account to continue.')
            return redirect (url_for('viewdecks'))
        
        try:
            terms = creator(text, prompt_option, prompt_option2, trans_option, lang_option, len_option, qmin_option, qmax_option)
        except:
            flash('It looks like our AI is being overworked!  Please try again in a moment')
            redirect('viewdecks')
        ## IF CHOSING TRANSSLATE SET CATEGORY TO LANGUAGE OTHERWISE TAKES ON TYPE OF CARD
        if prompt_option == "Translate":
            cat = prompt_option2
        else:
            cat = prompt_option
            
        ## DATA LOGGING
        try:
            for i in range (0, len(terms[1])):
                prompt = str(terms[1][i])
                response = str(terms[2][i])
                content = str(terms[3][i])
                response_entry = ResponseData(prompt=prompt, response=response, content=content, timestamp = datetime.now())
                db.session.add(response_entry)
                db.session.commit()

        except:
            print("no response data")

        terms = terms[0]
        ## SET USER TO CURRENT USER
        deck.user_id = current_user.id
        ## ADD CARDS TO DECK
        if prompt_option == "Mcq":
            v, w, x, y, z = mapping.get(prompt_option, ("A", "B", "C", "D", "E"))
            for item in terms:
                term = item[v].capitalize()
                exists = Card.query.filter_by(term=term).first()
                if exists:
                    print("card {} already exists".format(term))
                    continue
                entry = Card(category = cat, term=term, content=(add_period(item[w].capitalize())), boc_2=(add_period(item[x].capitalize())), boc_3=(add_period(item[y].capitalize())), boc_4=(add_period(item[z].capitalize())), create_method = method)
                db.session.add(entry)
                deck.cards.append(entry)
            db.session.commit()
        elif prompt_option != "Mcq" and prompt_option != "Transcribe" and prompt_option != "Formulas":
            x, y = mapping.get(prompt_option, ("A", "B"))
            for item in terms:
                term=item[x].capitalize()
                exists = Card.query.filter_by(term=term).first()
                if exists:
                    print("card {} already exists".format(term))
                    continue
                entry = Card(category = cat, term=term, content=add_period(item[y].capitalize()), create_method=method)
                db.session.add(entry)
                deck.cards.append(entry)
            db.session.commit()
        elif prompt_option == "Formulas":
            x, y, z = mapping.get(prompt_option, ("A", "B", "C"))
            for item in terms:
                term=item[x].capitalize()
                exists = Card.query.filter_by(term=term).first()
                if exists:
                    print("card {} already exists".format(term))
                    continue
                entry = Card(category = cat, term=term, formula="\["+(item[y])+"\]", content=add_period(item[z].capitalize()), create_method=method)
                db.session.add(entry)
                deck.cards.append(entry)
            db.session.commit()
        elif prompt_option == "Transcribe":
            if trans_option != None:
                name = deck.name + "_" + method + "_" + prompt_option + trans_option + "_" + str(datetime.utcnow())
                create_type = trans_option + " translation"
                transcript_trans = DeckFiles(file_name = name, text_string = terms, time_created = datetime.utcnow(), create_type = create_type)
                db.session.add(transcript_trans)
                deck.deck_files.append(transcript_trans)
                db.session.commit()
                return redirect("sea_dox/{deck.id}".format(deck = deck))
        ## ADD DECK) 
        if check_subscription_plan(current_user) == 5:       
            if form.generate_images.data == True: 
                for card in deck.cards:
                    try:
                        card.img = create_image(card.term)
                        db.session.commit()
                    except:
                        pass       
        ## SAVE TEXT TO DB
        f_name = deck.name + "_" + method + "_" + prompt_option + "_" + str(datetime.utcnow())
        file_storage = DeckFiles(file_name=f_name, text_string=text, create_type = "source", time_created = datetime.utcnow())
        db.session.add(file_storage) 
        deck.deck_files.append(file_storage)
        db.session.commit() 
        return redirect('/carousel/{deck.id}'.format(deck = deck))
    else:
        print("form not valid")
        print("name", form.name.data, "/n", "description" ,form.description.data, "/n", "deck_list", form.deck_list.data, "/n", "prompt", form.prompt.data, "/n", "text_input", form.text_input.data, "/n", "file", form.file.data)
    return render_template("extract.html", title="Extract", form=form)









def extract_terms(text: str, prompt_options: dict):
    print("entered extract term function")
    print(prompt_options)
    
    
    retries = 0
    main_opt = prompt_options['main_opt']
    subject_opt = prompt_options['subject_opt']
    trans_opt = prompt_options['trans_opt']
    lang_opt = prompt_options['lang_opt']
    detail_lvl_opt = prompt_options['detail_lvl_opt']
    min_opt = prompt_options['min_opt']
    max_opt = prompt_options['max_opt']
    
    user_prompt = build_prompt(prompt_options)
    
    
    while retries < 3:
        
        
        
        
        print("attempt:", retries)
        try:
            ## get prompt choice
            prompt_select = prompt_choices[main_opt]
            ## get prompt chocie 2
            if subject_opt != None:
                subject = "related to the subject of " + prompt_choices2[subject_opt]
            else:
                subject = ""
            ## get language
            if lang_opt!= None:
                lang = lang_choices[lang_opt]
            else:
                lang = ""
            ## get len_option
            if detail_lvl_opt:
                detail = len_choices[detail_lvl_opt]
            else:
                detail = ""
            if min_opt:
                qmin = "at least " + min_opt 
            else:
                qmin = "all"
            if max_opt:
                qmax = ", and at most " + max_opt
            else:
                qmax = ""
            if subject_opt:    
                option_2 = prompt_choices2[subject_opt]
            elif trans_opt:
                option_2 = trans_opt

            sys_instruct = f"You are a helpful teacher who wants to help students learn {subject_opt}."
            if main_opt not in prompt_choices:
                raise ValueError("Invalid prompt option")
            prompt_select = prompt_select.replace('{qmin}', qmin)
            prompt_select = prompt_select.replace('{c2}', subject)
            prompt_select = prompt_select.replace('{qmax}', qmax)
            prompt_select = prompt_select.replace('{length}', detail)
            prompt_select = prompt_select.replace('{lang}', lang)

            if trans_opt != None:
                print(prompt_select)
                prompt_select = prompt_select.replace('{option_2}', option_2)

            user_prompt = (prompt_select + text + 'The JSON object: \n')
            response = call_ai_terms(sys_instruct, user_prompt)

            response_ = response['choices'][0]['message']['content'].strip()


            if main_opt == "Cloze":
                response_ = add_underscores(response_)
                
            byte_string = response_.encode('utf-8')
            x = byte_string.decode('utf-8')

            x = json.loads(x)

            return x, user_prompt, response, x
        except Exception as e:
            retries += 1
            print(f"Error: {e}. Retrying ({retries}/3)")
   