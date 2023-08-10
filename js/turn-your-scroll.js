const fromWords = [
    "youtube video",
    "podcasts",
    "lecture notes",
    "academic papers",
    "newspaper articles",
    "wikipedia links",
    "assigned readings",
    "voice memos",
  ];
  
  const toWords = [
    "Definition Flashcards",
    "Formula flashcards",
    "Multiple choice questions",
    "Fill in the blank questions",
    "Comprehension questions",
    "Test questions and answers",
    "summaries",
    "detailed notes",
    "poems",
  ];
  
  const fromElement = document.getElementById("from");
  const toElement = document.getElementById("to");
  
  function getRandomElement(array) {
    return array[Math.floor(Math.random() * array.length)];
  }
  
  function updateWords() {
    fromElement.textContent = getRandomElement(fromWords);
    toElement.textContent = getRandomElement(toWords);
  }
  
  setInterval(updateWords, 4000);