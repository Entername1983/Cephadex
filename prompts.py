prompt_choices = {
    'Definitions': ' Given the passage below, extract {qmin} {qmax} uncommon or technical terms {subject} and provide a detailed and extensive definition for each. {lang} Create a JSON object which enumerates a set of child objects. Each of the child objects should correspond to one of the terms extracted and have a property named "A" as well as one named "B". \n The resulting JSON object should be in this format: [{"A":"term","B":"definition"}] \n The passage: \n',
    "Translate": 'Given the passage below, extract {qmin} {qmax} uncommon or technical terms {subject} and provide a {trans} translation for each. Create a JSON object which enumerates a set of child objects. Each of the child objects should correspond to one of the terms extracted and have a property named "A", for the term, as well as one named "B", for the {trans} translation. \n The resulting JSON object should be in this format: [{"A":"term","B":"translation"}] \n The passage: \n',
    "Rhyme": 'Given the passage below, extract {qmin} {qmax} uncommon or technical terms {subject} and create a four verse poem for each {lang}. Create a JSON object which enumerates a set of child objects. Each of the child objects should correspond to one of the terms extracted and have a property named "A", for the term, as well as one named "B", for the poem. \n The resulting JSON object should be in this format: [{"A":"term","B":"poem"}] \n The passage: \n',
    "People": 'Given the passage below, extract all the names of people and provide a {length} biography for each {lang}. Create a JSON object which enumerates a set of child objects. Each of the child objects should correspond to one of the terms extracted and have a property named "A", for the person, as well as one named "B", for the biography. \n The resulting JSON object should be in this format: [{"A":"string","B":"string"}] \n The passage: \n',    
    "Theories": 'Given the passage below, identify {qmin} {qmax} relevant theories and concepts {subject} and provide an {length} explanation for each {lang}. Create a JSON object which enumerates a set of child objects. Each of the child objects should correspond to one of the theories or concepts extracted and have a property named "A", for the theory or concept, as well as one named "B", for the explanation. \n The resulting JSON object should be in this format: [{"A":"string","B":"string"}] \n The passage: \n',
    "Cloze": 'Given the passage below, create {qmin} {qmax} fill in the blank questions {lang}.{subject} The goal is to test my understanding of the text. Create a JSON object which enumerates a set of child objects. Each of the child objects should correspond to one of the cloze deletion texts and have a property named "A" for the text to be filled in and have underscores "_____" to mark where the answer should go, and "B" for the missing word(s). \n The resulting JSON object should be in this format: [{"A":"string","B":"string"}] \n The passage: \n',
    "Mcq":'{subject} Given the passage below, create {qmin} {qmax} {length} multiple choice questions {lang}. Create a JSON object which enumerates a set of child objects. Each of the child objects should correspond to one of the multiple choice questions and have a property named "A" for the question, one named "B" for the correct answer and 3 other properties for the wrong answers, "C", "D", "E". \n The resulting JSON object should be in this format: [{"A": "string", "B":"Answer", "C":"Wrong answer 1", "D":"Wrong answer 2", "E":"Wrong answer 3"}] \n The passage \n',
    "Comprehension":'Given the passage below, create {qmin}  {qmax} {length} questions to test comprehension of the key information contained within {subject} {lang}. Create a JSON object which enumerates a set of child objects. Each of the child objects should correspond to one of the comprehension questions and have a property named "A" for the question, and "B" for the answer. \n The resulting JSON object should be in this format: [{"A":"string","B":"string"}] \n The passage: \n',    
    "Vocab_builder": 'Given the passage below, extract all unique words and provide a definition for each.  Create a JSON object which enumerates a set of child objects.  Each of the child objects should correspond to one of the words extracted and have a property named "A", for the word, as well as one named "B", for the definition. \n The resulting JSON object should be in this format: [{"A":"string","B":"string"}] \n The passage: \n',
    "Formulas": 'Given the passage below, extract all mentions of math or scientic formulas or terms, and provide the name of the formula (or term), the formula itself (or formula associated with the term) in LaTeX format, and an explanation of the formula.  Create a JSON object which enumerates a set of child objects.  Each of the child objects should correspond to one of the formulas extracted and have a property named "A", for the name of the formula, "B" for the formula itself in latex format, and "C" for the explanation of the formula.  \n The resulting JSON object should be in this format: [{"A":"name of formula","B":"LaTeX formula","C":"explanation of formula"}] \n The passage: \n',
    "Custom": 'Given the passage below, extract {qmin} {qmax} {custom_term}, and provide a {length} {custom_content} for each. {subject} Create a JSON object which enumerates a set of child objects. Each of the child objects should correspond to one of the {custom_term} extracted and have a property named "A" as well as one named "B" for the {custom_content} provided. \n The resulting JSON object should be in this format: [{"A":"{custom_term}","B":"{custom_content}"}] \n The passage: \n',
    "Explain": 'Given the passage below, create a series of question meant to test students ability to understand concepts in the passage as defined in Blooms taxonomy.  Questions should start with with explain.  Additionally provide a sample answer to each question.  Create a JSON object which enumerates a set of child objects.  Each of the child objects should correspond to one of hte questions and have a property named "A" as well as one named "B" corresponding to the sample answer. \n The resulting JSON object should be in this format: "[{"A":"Question","B":"Sample answer"] \n The passage: \n',
    "Discuss": 'Given the passage below, create debate topics related to the content of the text as well as arguments for and against each side.  Each debate topic should start with the word "Discuss.. Create a JSON object which enumerates a set of child objects. Each of the child objects should correspond to one of the debate topics extracted and have a property named "A" for the question, one named "B" containing the arguments for and against. \n The resulting JSON object should be in this format: "[{"A":"Discuss question","B":"1 - Arguments for: ... 2 - Argumnets against: ..."] \n The passage: \n',
    } 

bloom_choices = {
    "Remember": "Remembering",
    "Understand": "Understanding",
    "Apply": "Applying",
    "Analyze": "Analyzing",
    "Evaluate": "Evaluating",
    "Create": "Creating",
    }

prompt_from_scratch = {
    'Definitions': '''Create at least 10 definitions on the subject of {subject} and the
    topic of {topic} as you can.  The definitions should be related to the following
    concepts {concepts} and be appropriate for a {grade} student.  
    Create a JSON object which enumerates a set of child objects. 
    Each of the child objects should correspond to one of the terms extracted and
    have a property named "A" as well as one named "B". \n The resulting JSON 
    object should be in this format: [{"A":"term","B":"definition"}] 
    \n The passage: \n''',

    "Theories": '''Create at least 10 theory explanation questions on the subject of {subject} 
    and the topic of {topic} as you can. The questions should be related to the following
    concepts {concepts} and be appropriate for a {grade} student. Create a JSON object
    which enumerates a set of child objects. Each of the child objects should 
    correspond to one of the theories or concepts extracted and have a property named
    "A", for the theory or concept, as well as one named "B", for the explanation.
    \n The resulting JSON object should be in this format: 
    [{"A":"string","B":"string"}] \n The passage: \n''',

    "Cloze": '''Create at least 10 cloze deletion questions on the subject of {subject} and 
    the topic of {topic} as you can.  The questions should be related to the following 
    concepts {concepts} and suitable for {grade} students. Create a JSON object which enumerates a set of child objects. 
    Each of the child objects should correspond to one of the cloze deletion texts and 
    have a property named "A" for the text to be filled in and have underscores "_____" 
    to mark where the answer should go, and "B" for the missing word(s). \n 
    The resulting JSON object should be in this format: [{"A":"string","B":"string"}] 
    \n The passage: \n''',

    "Mcq":'''Create at least 10 multiple choice questions on the subject of {subject} and 
    the topic of {topic} as you can.  The questions should be related to the following 
    concepts {concepts}and suitable for {grade} students. Create a JSON object which enumerates a set of child objects. 
    Each of the child objects should correspond to one of the multiple choice questions 
    and have a property named "A" for the question, one named "B" for the correct answer 
    and 3 other properties for the wrong answers, "C", "D", "E". \n 
    The resulting JSON object should be in this format: [{"A": "string", "B":"Answer",
      "C":"Wrong answer 1", "D":"Wrong answer 2", "E":"Wrong answer 3"}] \n The passage
        \n''',
    "Comprehension":'''Create at least 10 comprehension questions on the subject of {subject} and 
    the topic of {topic} as you can.  The questions should be related to the following 
    concepts {concepts}and suitable for {grade} students. Create a JSON object which enumerates a set of child objects. 
    Each of the child objects should correspond to one of the comprehension questions 
    and have a property named "A" for the question, and "B" for the answer. \n 
    The resulting JSON object should be in this format: [{"A":"string","B":"string"}] 
    \n The passage: \n''',    
    "Formulas": '''The subject is {subject}, the topic is {topic} and the main concepts
    are {concepts} identify at least 10 related formulas or terms suitable for {grade} students, 
    and provide the name of the 
    formula (or term), the formula itself (or formula associated with the term) in 
    LaTeX format, and an explanation of the formula.  Create a JSON object which 
    enumerates a set of child objects.  Each of the child objects should correspond
    to one of the formulas extracted and have a property named "A", for the name of
    the formula, "B" for the formula itself in latex format, and "C" for the 
    explanation of the formula.  \n The resulting JSON object should be in this 
    format: [{"A":"name of formula","B":"LaTeX formula","C":"explanation of formula"}] 
    \n The passage: \n''',
    "Explain": '''Create at least 10 questions meant to test {grade} students ability
    to understand the topic of {topic} as part of the subject of {subject} 
    and the concepts of {concepts} in the passage as defined in Blooms taxonomy.  
    Questions should start with with explain.  Additionally provide a sample answer 
    to each question.  Create a JSON object which enumerates a set of child objects.  
    Each of the child objects should correspond to one of hte questions and 
    have a property named "A" as well as one named "B" corresponding to the sample 
    answer. \n The resulting JSON object should be in this format: 
    "[{"A":"Question","B":"Sample answer"] \n The passage: \n''',
    "Discuss": '''Create at least 8 debate topics on the topic of {topic} 
    in the subject of {subject} that are appropriate for {grade} students and test 
    their understanding of {concepts} well as arguments for and against each side.  
    Each debate topic should start with the word "Discuss.. Create a JSON object which 
    enumerates a set of child objects. Each of the child objects should correspond to 
    one of the debate topics extracted and have a property named "A" for the question, 
    one named "B" containing the arguments for and against. \n The resulting JSON object 
    should be in this format: "[{"A":"Discuss question","B":"1 - Arguments for: ... 2 - 
    Argumnets against: ..."] \n The passage: \n''',
    } 


prompt_choices2 =  {
    "Econ": "Economics",
    "Finance": "Finance",
    "Lit": "Literature",
    "Chem": "Chemistry",
    "Science":  "Science",
    "Physics": "Physics",
    "Philo": "Philosophy",
    "CS": "Computer Science",
    "Bio": "Biology",
    "Math": "Mathematics",
    "Geo": "Geography",
    "Hist": "History",
    "Anatomy": "Anatomy",
    "Psych": "Psychology",
    "Soc": "Sociology",
    "Law": "Law",
    "Music": "Music",
    "Art": "Art",
    "Dance": "Dance",
    "Theatre": "Theatre",
    "Film": "Film",
    "Med": "Medicine",
    "Eng": "Engineering",
    "Bus": "Business",
    "Politics": "Political science",
    }
lang_choices = {
    "English": "The language used should be English",
    "French": "The language used should be French",
    "Spanish": "The language used should be Spanish",
    "German": "The language used should be German",
    "Portuguese": "The language used should be Portuguese",
    "Chinese": "The language used should be Chinese",
    "Russian": "The language used should be Russian",
    "Swahili": "The language used should be Swahili",
    "Japanese": "The language used should be Japanese",
    "Dothraki": "The language used should be Dothraki",
    "Klingon": "The language used should be Klingon",
    "Dutch": "The language used should be Dutch",
    "Italian": "The language used should be Italian",
    "Greek": "The language used should be Greek",
    "Arabic": "The language used should be Arabic",
    "Hindi": "The language used should be Hindi",
    "Polish": "The language used should be Polish",
    "Hebrew": "The language used should be Hebrew",
    "Finnish": "The language used should be Finnish",
    "Norwegian": "The language used should be Norwegian",
    "Swedish": "The language used should be Swedish",
    "Turkish": "The language used should be Turkish",
    "Czech": "The language used should be Czech",
    "Romanian": "The language used should be Romanian",
    "Hungarian": "The language used should be Hungarian",
    "Bulgarian": "The language used should be Bulgarian",
    "Croatian": "The language used should be Croatian",
    "Serbian": "The language used should be Serbian",
    "Estonian": "The language used should be Estonian",
    "Latvian": "The language used should be Latvian",
    "Lithuanian": "The language used should be Lithuanian",
    "Farsi": "The language used should be Farsi",
    "Korean": "The language used should be Korean",
    "Indonesian": "The language used should be Indonesian",
    "Vietnamese": "The language used should be Vietnamese",
    "Urdu": "The language used should be Urdu",
    "Persian": "The language used should be Persian",
    "Thai": "The language used should be Thai",
    "Malay": "The language used should be Malay",
    "Tagalog": "The language used should be Tagalog",
    }

len_choices = {
    "long": "very long",
    "short": "short",}







###########ALTERNATIVE prompts VERSION

new_prompt_choices = {
    'Definitions': ' Given the passage below, extract {qmin} {qmax} uncommon or technical terms {subject} and provide a {length} definition for each. {lang} Output each term starting with a "$@$" and ending with "$$", have each definition start with "@$@" and end with "@@" like in the following example: $@$"Key":"term"$$ @$@"Value":"definition"@@ ',
    "Translate": 'Given the passage below, extract {qmin} {qmax} uncommon or technical terms {subject} and provide a {trans} translation for each. Create a JSON object which enumerates a set of child objects. Each of the child objects should correspond to one of the terms extracted and have a property named "A", for the term, as well as one named "B", for the {option_2} translation. \n The resulting JSON object should be in this format: [{"A":"term","B":"translation"}] \n The passage: \n',
    "Rhyme": 'Given the passage below, extract {qmin} {qmax} uncommon or technical terms {subject} and create a four verse poem for each {lang}. Create a JSON object which enumerates a set of child objects. Each of the child objects should correspond to one of the terms extracted and have a property named "A", for the term, as well as one named "B", for the poem. \n The resulting JSON object should be in this format: [{"A":"term","B":"poem"}] \n The passage: \n',
    "People": 'Given the passage below, extract all the names of people and provide a {length} biography for each {lang}. Create a JSON object which enumerates a set of child objects. Each of the child objects should correspond to one of the terms extracted and have a property named "A", for the person, as well as one named "B", for the biography. \n The resulting JSON object should be in this format: [{"A":"string","B":"string"}] \n The passage: \n',    
    "Theories": 'Given the passage below, identify {qmin} {qmax} relevant theories and concepts {subject} and provide an {length} explanation for each {lang}. Create a JSON object which enumerates a set of child objects. Each of the child objects should correspond to one of the theories or concepts extracted and have a property named "A", for the theory or concept, as well as one named "B", for the explanation. \n The resulting JSON object should be in this format: [{"A":"string","B":"string"}] \n The passage: \n',
    "Cloze": 'Given the passage below, create {qmin} {qmax} cloze deletion questions  {lang}.{subject} The goal is to test my understanding of the text. Create a JSON object which enumerates a set of child objects. Each of the child objects should correspond to one of the cloze deletion texts and have a property named "A" for the cloze deletion text, and "B" for the missing word(s). \n The resulting JSON object should be in this format: [{"A":"string","B":"string"}] \n The passage: \n',
    "Mcq":'{subject} Given the passage below, create {qmin} {qmax} {length} multiple choice questions {lang}. Create a JSON object which enumerates a set of child objects. Each of the child objects should correspond to one of the multiple choice questions and have a property named "A" for the question, one named "B" for the correct answer and 3 other properties for the wrong answers, "C", "D", "E". \n The resulting JSON object should be in this format: [{"A": "string", "B":"Answer", "C":"Wrong answer 1", "D":"Wrong answer 2", "E":"Wrong answer 3"}] \n The passage \n',
    "Comprehension":'Given the passage below, create {qmin}  {qmax} {length} questions to test comprehension of the key information contained within {subject} {lang}. Create a JSON object which enumerates a set of child objects. Each of the child objects should correspond to one of the comprehension questions and have a property named "A" for the question, and "B" for the answer. \n The resulting JSON object should be in this format: [{"A":"string","B":"string"}] \n The passage: \n',    
    "Vocab_builder": 'Given the passage below, extract all unique words and provide a definition for each.  Create a JSON object which enumerates a set of child objects.  Each of the child objects should correspond to one of the words extracted and have a property named "A", for the word, as well as one named "B", for the definition. \n The resulting JSON object should be in this format: [{"A":"string","B":"string"}] \n The passage: \n',
    "Formulas": 'Given the passage below, extract all mentions of math or scientic formulas or terms, and provide the name of the formula (or term), the formula itself (or formula associated with the term) in LaTeX format, and an explanation of the formula.  Create a JSON object which enumerates a set of child objects.  Each of the child objects should correspond to one of the formulas extracted and have a property named "A", for the name of the formula, "B" for the formula itself in latex format, and "C" for the explanation of the formula.  \n The resulting JSON object should be in this format: [{"A":"name of formula","B":"LaTeX formula","C":"explanation of formula"}] \n The passage: \n',
    } 

regen_choices = {
    'Definitions': 'Provide a {length} definition for the following term {term} {lang}',
    "Translate": 'Provide a {length} translation for the following term {term} {lang}',
    "Rhyme": 'Create a four verse poem for the following term {term} {lang}.',
    "People": 'Provide a {length} biography for the following person {term} {lang}',    
    "Theories": 'Provide a {length} explanation for the following theory or concept {term} {lang}',
    "Cloze": 'Provide a {length} definition for the following term {term} {lang}',
    "Mcq": 'Create 4 multiple choice answers for the following question {term} {lang}. 1 answer should be correct, the other 3 should be incorrect.',
    "Comprehension":'Create a {length} question to test comprehension of {term} {lang}.',  
    "Vocab_builder": 'Provide a {length} definition for the following term {term} {lang}',
    "Formulas": 'Provide a detailed explanation of the following formula {term} {lang}',
    "Custom": 'Provide a {length} definition for the following term {term} {lang}',
    } 
