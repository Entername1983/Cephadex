@app.route("/currentdeck2/<deck_id>", methods =["GET", "POST"])
@login_required
def currentdeck2(deck_id):

## Card like Dish
## Deck like Restaurante
    cards = Card.query.filter(Card.decks.any(id=deck_id)).all()
    deck = deck_id

    return render_template('currentdeck2.html', cards=cards, deck_id=deck)



@app.route("/editcard/<int:deck_id>/<int:card_id>", methods = ["POST", "GET"])
def editcard(card_id, deck_id):
    id = card_id
    card = Card.query.filter_by(id=id).first()
    deck = deck_id
    form = EditCard()
    if form.validate_on_submit():
        card = Card.query.filter_by(id=id).first()
        card.term = form.term.data
        card.content = form.content.data
        db.session.commit()
        return redirect(("/currentdeck/{deck}").format(deck=deck))
    
    return render_template("editcard.html", title="Edit Card", form=form, card=card)



@app.route("/cardeditor/<deck_id>", methods = ["POST", "GET"])
@login_required
def cardeditor():

    if request.method == 'POST':
        field = request.form['field'] ## term or content
        value = request.form['value'] ## new value for term or content
        id = request.form['id'] ## id of card to be edited
        if field == 'term':
            card = Card.query.filter_by(id=id).first()
            card.term = value
            db.session.commit()
        elif field == 'content':
            card = Card.query.filter_by(id=id).first()
            card.content = value
            db.session.commit()        
        if request.form.get('delete'):
            card = Card.query.filter_by(id=id).first()
            db.session.delete(card)
            db.session.commit()
            
    return render_template("cardeditor.html", title="Card Editor")