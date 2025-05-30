# Spanish Divide Into Syllables in Python
# (Direct translation from the provided JavaScript code)

# some constants related to spanish language
import re
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from language_processors.spanish import process_text as es_processor


AlphabetEs = [
    "a",
    "b",
    "c",
    "d",
    "e",
    "f",
    "g",
    "h",
    "i",
    "j",
    "k",
    "l",
    "m",
    "n",
    "ñ",
    "o",
    "p",
    "q",
    "r",
    "s",
    "t",
    "u",
    "v",
    "w",
    "x",
    "y",
    "z",
]

vowels = ["a", "e", "i", "o", "u", "á", "é", "í", "ó", "ú"]
vowelsTilde = ["á", "é", "í", "ó", "ú"]
openVowels = ["a", "e", "o", "á", "é", "í", "ó", "ú"]
closedVowels = ["u", "i", "ü"]
consonants = [
    "b",
    "c",
    "d",
    "f",
    "g",
    "h",
    "j",
    "k",
    "l",
    "m",
    "n",
    "ñ",
    "p",
    "q",
    "r",
    "s",
    "t",
    "v",
    "w",
    "x",
    "y",
    "z",
]
possibleDobleLetters = ["r", "l", "t"]
unsplittables = [
    "br",
    "cr",
    "dr",
    "gr",
    "fr",
    "kr",
    "tr",
    "bl",
    "cl",
    "gl",
    "fl",
    "kl",
    "pl",
    "gü",
    "ch",
]


def aWsplittedF(analizedWord):
    """
    Takes a string and returns it split letter by letter
    """
    analizedWordSplit = list(analizedWord)
    return analizedWordSplit


def VowelOrConsonant(analizedWord):
    """
    Takes a string and returns an array that distinguishes
    between consonants, open vowels and closed vowels.
    e.g. ['c', 'vO', 'vC', ...]
    """
    wordProcesed = []
    for i in range(len(analizedWord)):
        letterRecognized = False
        isVowel = False
        # check if it's a vowel
        for e in range(len(vowels)):
            if vowels[e] == analizedWord[i]:
                isVowel = True

        # if it isn't a vowel, it's a consonant
        if not isVowel:
            wordProcesed.append("c")
        else:
            # if it's a vowel, check if it's closed
            for d in range(len(closedVowels)):
                if closedVowels[d] == analizedWord[i] and not letterRecognized:
                    wordProcesed.append("vC")
                    letterRecognized = True
                    break
            if not letterRecognized:
                wordProcesed.append("vO")
                letterRecognized = True
    return wordProcesed


def getIndicesOf(searchStr, string, caseSensitive=True):
    """
    Searches for `searchStr` in `string` and returns a list of indices
    where `searchStr` begins.
    """
    searchStrLen = len(searchStr)
    if searchStrLen == 0:
        return []

    if not caseSensitive:
        lower_string = string.lower()
        lower_searchStr = searchStr.lower()
    else:
        lower_string = string
        lower_searchStr = searchStr

    startIndex = 0
    indices = []
    while True:
        index = lower_string.find(lower_searchStr, startIndex)
        if index == -1:
            break
        indices.append(index)
        startIndex = index + searchStrLen

    return indices


def indexOfVowels(aWvowelOrConsonant):
    """
    Finds vowels in the VowelOrConsonant array and returns indices of them.
    """
    ubicationVowels = []
    for i in range(len(aWvowelOrConsonant)):
        if aWvowelOrConsonant[i] == "vO" or aWvowelOrConsonant[i] == "vC":
            ubicationVowels.append(i)
    return ubicationVowels


def findDiptongos(aWSplitted):
    """
    Finds diptongos in the splitted array and returns their indices.
    """
    diptongosIndex = []
    for i in range(len(aWSplitted)):
        # check if there is a closed vowel
        if aWSplitted[i] == "i" or aWSplitted[i] == "u":
            # check vowel before
            if i - 1 >= 0:
                if aWSplitted[i - 1] in vowels:
                    diptongosIndex.append(i - 1)
            # check vowel after
            if i + 1 < len(aWSplitted):
                if aWSplitted[i + 1] in vowels:
                    diptongosIndex.append(i)

    # eliminate duplicates
    uniqueArray = []
    for item in diptongosIndex:
        if item not in uniqueArray:
            uniqueArray.append(item)
    return uniqueArray


def findHiatos(aWSplitted):
    """
    Finds hiatos in the splitted array and returns their indices.
    """
    hiatosIndex = []
    for i in range(len(aWSplitted)):
        # check if there is an open vowel
        if aWSplitted[i] in openVowels:
            # check next letter
            if i + 1 < len(aWSplitted):
                if aWSplitted[i + 1] in openVowels:
                    hiatosIndex.append(i)

    # eliminate duplicates
    uniqueArray = []
    for item in hiatosIndex:
        if item not in uniqueArray:
            uniqueArray.append(item)
    return uniqueArray


def findDobleLetters(aWSplitted):
    """
    Finds rr, ll, etc., in the splitted array and returns their indices.
    """
    dobleLettersIndex = []
    for i in range(len(aWSplitted)):
        for e in range(len(possibleDobleLetters)):
            if aWSplitted[i] == possibleDobleLetters[e]:
                if (i + 1 < len(aWSplitted)) and (aWSplitted[i] == aWSplitted[i + 1]):
                    dobleLettersIndex.append(i)

    # eliminate duplicates
    uniqueArray = []
    for item in dobleLettersIndex:
        if item not in uniqueArray:
            uniqueArray.append(item)
    return uniqueArray


def getIndicesOfThese(findThese, text):
    """
    Finds an array of strings in `text` and returns the indices of them.
    """
    arr = []
    for i in range(len(findThese)):
        indices_found = getIndicesOf(findThese[i], text, caseSensitive=True)
        arr.extend(indices_found)
    mergedNsorted = sorted(arr)
    uniqueArray = []
    for item in mergedNsorted:
        if item not in uniqueArray:
            uniqueArray.append(item)
    return uniqueArray


def findUnsplittables(analizedWord):
    """
    Finds unsplittable strings and returns their indices.
    """
    return getIndicesOfThese(unsplittables, analizedWord)


def aWanalysis(analizedWord):
    """
    Returns a full word analysis based on the info returned by the helper functions.
    """
    lowerWord = analizedWord.lower()
    splitted = aWsplittedF(lowerWord)
    vOrC = VowelOrConsonant(lowerWord)
    analysis = {
        "aWoriginal": analizedWord,
        "analizedWord": lowerWord,
        "aWSplitted": splitted,
        "aWvowelOrConsonant": vOrC,
        "aWindexOfVowels": indexOfVowels(vOrC),
        "indexOfDiptongos": findDiptongos(splitted),
        "indexOfHiatos": findHiatos(splitted),
        "indexOfdobleLetters": findDobleLetters(splitted),
        "indexOfunsplittables": findUnsplittables(lowerWord),
        "aWTotalySplitted": False,
    }
    return analysis


def cutASyllable(analizedWord):
    """
    Receives a string and returns an array: ['first syllable', 'the rest'].
    """
    # Pull all needed indices from the analysis
    analysis = aWanalysis(analizedWord)

    # For brevity, we'll alias them as used in JS
    firstVowelIndex = (
        analysis["aWindexOfVowels"][0] if len(analysis["aWindexOfVowels"]) > 0 else None
    )
    secondVowelIndex = (
        analysis["aWindexOfVowels"][1] if len(analysis["aWindexOfVowels"]) > 1 else None
    )
    thirdVowelIndex = (
        analysis["aWindexOfVowels"][2] if len(analysis["aWindexOfVowels"]) > 2 else None
    )

    firstHiatoIndex = (
        analysis["indexOfHiatos"][0] if len(analysis["indexOfHiatos"]) > 0 else None
    )
    firstDiptongoIndex = (
        analysis["indexOfDiptongos"][0]
        if len(analysis["indexOfDiptongos"]) > 0
        else None
    )
    firstUnsplittableIndex = (
        analysis["indexOfunsplittables"][0]
        if len(analysis["indexOfunsplittables"]) > 0
        else None
    )
    firstRepeatedLetterIndex = (
        analysis["indexOfdobleLetters"][0]
        if len(analysis["indexOfdobleLetters"]) > 0
        else None
    )

    if firstVowelIndex is not None and secondVowelIndex is not None:
        consonantsBetweenVowels = secondVowelIndex - firstVowelIndex
    else:
        consonantsBetweenVowels = None

    wordBeingCut = None
    firstSyllable = None

    def cutFirstSyllableHere(whereToCut):
        nonlocal firstSyllable, wordBeingCut
        firstSyllable = analizedWord[0:whereToCut]
        wordBeingCut = analizedWord[whereToCut:]

    # Here are the splitting rules
    if len(analizedWord) < 2:
        # if the entire word length is less than 2, just cut at the end
        cutFirstSyllableHere(len(analizedWord))
    elif (
        firstVowelIndex is not None
        and firstHiatoIndex is not None
        and firstVowelIndex == firstHiatoIndex
    ):
        # if there is a hiato and it's at the first vowel
        cutFirstSyllableHere(firstHiatoIndex + 1)
    elif (
        firstVowelIndex is not None
        and firstDiptongoIndex is not None
        and firstVowelIndex == firstDiptongoIndex
    ):
        # if there is a diptongo at the first vowel
        if thirdVowelIndex is not None:
            if firstRepeatedLetterIndex is not None and (
                firstVowelIndex + 2 == firstRepeatedLetterIndex
            ):
                cutFirstSyllableHere(thirdVowelIndex - 2)
            else:
                cutFirstSyllableHere(thirdVowelIndex - 1)
        else:
            # fallback if thirdVowelIndex doesn't exist
            cutFirstSyllableHere(len(analizedWord))
    elif (
        secondVowelIndex is not None
        and firstRepeatedLetterIndex is not None
        and secondVowelIndex - 2 == firstRepeatedLetterIndex
    ):
        cutFirstSyllableHere(secondVowelIndex - 2)
    elif (
        secondVowelIndex is not None
        and firstVowelIndex is not None
        and (secondVowelIndex - 5 == firstVowelIndex)
    ):
        cutFirstSyllableHere(secondVowelIndex - 2)
    elif (
        secondVowelIndex is not None
        and firstVowelIndex is not None
        and (secondVowelIndex - 4 == firstVowelIndex)
    ):
        # three consonants between vowels
        if firstUnsplittableIndex is not None and firstUnsplittableIndex == (
            firstVowelIndex + 1
        ):
            cutFirstSyllableHere(firstVowelIndex + 3)
        elif firstUnsplittableIndex is not None and firstUnsplittableIndex == (
            firstVowelIndex + 2
        ):
            cutFirstSyllableHere(firstVowelIndex + 2)
        else:
            cutFirstSyllableHere(firstVowelIndex + 3)
    elif (
        secondVowelIndex is not None
        and firstVowelIndex is not None
        and (secondVowelIndex - 3 == firstVowelIndex)
    ):
        # two consonants between vowels
        if firstUnsplittableIndex is not None and firstUnsplittableIndex == (
            firstVowelIndex + 1
        ):
            cutFirstSyllableHere(firstVowelIndex + 1)
        else:
            cutFirstSyllableHere(firstVowelIndex + 2)
    else:
        # if none of the above,
        # (either there's one consonant between vowels or other fallback)
        if secondVowelIndex is not None:
            cutFirstSyllableHere(secondVowelIndex - 1)
        else:
            # fallback if there's no second vowel
            cutFirstSyllableHere(len(analizedWord))

    if firstSyllable == "":
        wordProcess = [wordBeingCut]
    elif firstSyllable == "":
        # This condition is identical to above; original JS has it repeated.
        wordProcess = [wordBeingCut]
    else:
        wordProcess = [firstSyllable, wordBeingCut]

    return wordProcess


def split_syllables(s: str):
    """
    Receives a string and returns an array of its syllables
    by repeatedly using cutASyllable().
    """
    # Preprocess text using es_processor
    s = es_processor(s)

    # Word splitting logic
    words = re.findall(r"[a-zA-ZÀ-ÿ]+(?:'[a-zA-ZÀ-ÿ]+)?", s)

    count = 0
    syllables = []

    for w in words:
        IsThereLeftToCut = True
        splittedWord = []
        leftToCut = w

        def cutAgain():
            nonlocal leftToCut, IsThereLeftToCut
            cutted = cutASyllable(leftToCut)
            splittedWord.append(cutted[0])
            if len(cutted) > 1:
                leftToCut = cutted[1]
            else:
                # if there's nothing left
                IsThereLeftToCut = False
                return

            if len(cutted) <= 1 or len(leftToCut) < 1:
                IsThereLeftToCut = False

            if IsThereLeftToCut:
                cutAgain()

        cutAgain()

        if splittedWord:
            syllables.extend(splittedWord)
            count += len(splittedWord)
        else:
            syllables.append(w)
            count += 1
    return syllables, count


# array of words and correct spelling for testing
testedValues = [
    (["a"], ["a"]),
    (["águila"], ["á", "gui", "la"]),
    (["abril"], ["a", "bril"]),
    (["averigüéis"], ["a", "ve", "ri", "güéis"]),
    (["ren"], ["ren"]),
    (["contra"], ["con", "tra"]),
    (["instaurar"], ["ins", "tau", "rar"]),
    (["acróbata"], ["a", "cró", "ba", "ta"]),
    (["esdrújulo"], ["es", "drú", "ju", "lo"]),
    (["gato"], ["ga", "to"]),
    (["perro"], ["pe", "rro"]),
    (["alerta"], ["a", "ler", "ta"]),
    (["atraco"], ["a", "tra", "co"]),
    (["centellear"], ["cen", "te", "lle", "ar"]),
    (["plenitud"], ["ple", "ni", "tud"]),
    (["Esti"], ["Es", "ti"]),
    (["terremoto"], ["te", "rre", "mo", "to"]),
    (["perro"], ["pe", "rro"]),
    (["canario"], ["ca", "na", "rio"]),
    (["callo"], ["ca", "llo"]),
    (["abstracto"], ["abs", "trac", "to"]),
    (["perrito,Hello World"], ["pe", "rri", "to,", "He", "llo", "World"]),
    (
        ["""Mamá123123 but you are42"""],
        [],
    ),
]


def arraysMatch(arr1, arr2):
    """
    Check if two lists are the same length
    and all items exist in the same order.
    """
    if len(arr1) != len(arr2):
        return False
    for i in range(len(arr1)):
        if arr1[i] != arr2[i]:
            return False
    return True


def testWordSplitting(analizedWord, wordSpelledCorrect):
    """
    Test an individual word against the expected correct splitting.
    """
    autoCuttedWord, _ = split_syllables(analizedWord)
    if arraysMatch(autoCuttedWord, wordSpelledCorrect):
        print("ok")
        return True
    else:
        print("error", analizedWord, autoCuttedWord, wordSpelledCorrect)
        return [analizedWord, autoCuttedWord, wordSpelledCorrect]


def test(testedValues):
    """
    Test all words in testedValues and gather errors.
    """
    errorsArray = []
    for i in range(len(testedValues)):
        wordTestResult = testWordSplitting(testedValues[i][0][0], testedValues[i][1])
        if wordTestResult != True:
            errorsArray.append(wordTestResult)
    return errorsArray

