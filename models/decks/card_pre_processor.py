from .card_config import CARD_MAPPING

class CardPreProcessor:
    def __init__(self):
        self.mapping = CARD_MAPPING

    def preprocess(self, terms, card_type):
        if card_type == 'Mcq':
            return self.preprocess_mcq(terms)
        elif card_type == 'Formulas':
            return self.preprocess_formulas(terms)
        elif card_type == 'Discuss':
            return self.preprocess_discuss(terms)
        else:
            return self.preprocess_default(terms, card_type)

    def preprocess_default(self, terms, card_type):
        x, y = self.mapping.get(card_type, ("A", "B"))
        processed_terms = []
        for item in terms:
            term = item.get(x)
            term = ' '.join(term) if isinstance(term, list) else term
            term = term or None
            content = item.get(y)
            content = ' '.join(content) if isinstance(content, list) else content
            content = content or None
            processed_terms.append({term:{"content": content}})
        return processed_terms
    
    def preprocess_mcq(self, terms):
        v, w, x, y, z = self.mapping.get("Mcq", ("A", "B", "C", "D", "E"))
        processed_terms = []
        for item in terms:
            term = item.get(v)
            term = ' '.join(term) if isinstance(term, list) else term
            term = term or None
            content = item.get(w)
            content = ' '.join(content) if isinstance(content, list) else content
            content = content or None
            boc_2 = item.get(x)
            boc_2 = ' '.join(boc_2) if isinstance(boc_2, list) else boc_2
            boc_2 = boc_2 or None
            boc_3 = item.get(y)
            boc_3 = ' '.join(boc_3) if isinstance(boc_3, list) else boc_3
            boc_3 = boc_3 or None
            boc_4 = item.get(z)
            boc_4 = ' '.join(boc_4) if isinstance(boc_4, list) else boc_4
            boc_4 = boc_4 or None 
        processed_terms.append({term:{"content": content, "boc_2": boc_2,
                                       "boc_3": boc_3, "boc_4": boc_4}})
        return processed_terms

    def preprocess_formulas(self, terms):
        x, y, z = self.mapping.get("Formulas", ("A", "B", "C")) + (None,) * (3 - len(self.mapping.get("Formulas", ("A", "B", "C"))))
        processed_terms = []
        for item in terms:
            term = item.get(x)
            term = ' '.join(term) if isinstance(term, list) else term
            term = term or None
            formula = item.get(y)
            formula = ' '.join(formula) if isinstance(formula, list) else formula
            formula = "\[" + formula + "\]" if formula else None
            content = item.get(z)
            content = ' '.join(content) if isinstance(content, list) else content
            content = (content) if content else None
            processed_terms.append({term:{"formula": formula, "content": content}})
        return processed_terms
    
    def preprocess_discuss(self, terms):
        x, y, z = self.mapping.get("Discuss", ("A", "B", "C")) + (None,) * (3 - len(self.mapping.get("Discuss", ("A", "B", "C"))))
        processed_terms = []
        for item in terms:
            term = item.get(x)
            term = ' '.join(term) if isinstance(term, list) else term
            term = term or None
            side_1 = item.get(y)
            side_1 = ' '.join(side_1) if isinstance(side_1, list) else side_1
            side_1 = side_1 or None
            side_2 = item.get(z)
            if z is None:
                side_2 = None
            else:
                side_2 = ' '.join(side_2) if isinstance(side_2, list) else side_2
                side_2 = side_2 or None
            processed_terms.append({term: {"side_1": side_1, "side_2": side_2}})