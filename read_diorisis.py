import pickle
from xml.etree import ElementTree as ET
from collections import defaultdict
import math

NS_DICT = {
    'xml': '{http://www.w3.org/XML/1998/namespace}',
    'tei': '{http://www.tei-c.org/ns/1.0}'
}

BOOKNR = {
    "Iliad":1,
    "Odyssey":2
}

MINDWORDS = set([
 "θυμός", ## thumos
 "φρήν", ## phrenes
 "νόος", ## noos
 "ψυχή", ## psyche     
 "καρδία", ## kradie
 "ἔαρ", ## her
 "ἦτορ" ## etor
])

with open("stopwords_greek_homer.txt", "r") as swfile:
    STOPWORDS = [l.strip() for l in swfile.readlines()]

def get_lemmas_from_xml(xml_tree):
    path = "./text/body/sentence"
    lemmas = []
    for s in xml_tree.getroot().findall(path):
        sent = []
        for l in s.findall("./word/lemma"):
            if 'entry' in l.attrib:
                info = l.attrib
            else:
                continue
            try:
                info['morpho'] = [a.attrib["morph"].split() for a in l.findall("./analysis")]
            except KeyError:
                pass
            sent.append(info)
        lemmas.append(sent)
    return lemmas

def count_lemmas(lemmas):
    wordcount = {}
    for s in lemmas:
        for l in s:
            wordcount[l['entry']] = wordcount.get(l['entry'], 0) + 1
    return wordcount

def lemmas_and_wordcount_per_book(book):
    tree = ET.parse(f'Homer (0012) - {book} (00{BOOKNR[book]}).xml')
    lemmas = get_lemmas_from_xml(tree)
    try:
        with open(f'{book}_wc.pickle', 'rb') as infile:
            wc=pickle.load(infile)
    except FileNotFoundError:
        wc = count_lemmas(lemmas)
        with open(f'{book}_wc.pickle', 'wb') as f:
            pickle.dump(wc, f, pickle.HIGHEST_PROTOCOL)
    return lemmas, wc


def count_occurences_of_mind_words(book, normalize=False):
    _, wc = lemmas_and_wordcount_per_book(book)
    tot = sum(wc.values())
    print(f"number of distinct lemmata in {book}: {tot}")
    occ_tot = 0
    occs={}
    for word in MINDWORDS:
        try:
            occ = wc[word]
            occs[word] = occ
        except KeyError:
            occ = 0
        print(f"{word} occurs {occ} times in the {book}. normalized: {occ/tot*100000:.2f}/100000 words")
    occ_tot = sum(occs.values())
    print(f"All mind-related words occur {occ_tot} times in {book}. normalized: {occ_tot/tot*100000:.2f}/100000 words")
    print("--"*10)
    if normalize:
        return {mw:occs[mw]/tot*100000 for mw in occs}
    else:
        return occs

def analyse_embedding_of_mind_words(book):
    lemmas, wc = lemmas_and_wordcount_per_book(book)
    surroundings = get_surroundings_of_mind_words(lemmas, pos="verb")
    cooccurences = defaultdict(int)
    for key in surroundings:
        for sent in surroundings[key]:
            for word in sent:
                cooccurences[(key, word["entry"])] += 1
    pmi_index = pmi(wc, cooccurences, k=2)
    ranked = sorted(pmi_index.items(), reverse=True, key=lambda x:x[1])
    ranked_per_word={}
    for mindword in MINDWORDS:
        ranked_per_word[mindword]=[]
        for top in ranked:
            if top[0][0]==mindword:
                ranked_per_word[mindword].append((top[0][1], top[1]))
    return ranked_per_word, cooccurences, wc

def compare_mindword_embeddings(
        ranked_mindwords_odyssey,
        ranked_mindwords_iliad,
        cooccurences_odyssey,
        cooccurences_iliad, 
        wc_odyssey,
        wc_iliad,
        n_top_coocs=10
    ):
    for mindword in MINDWORDS:
        titlestr = f"| These are the {n_top_coocs} most correlated verbs with the mindword {mindword} in Iliad and Odyssey |"
        print(f'+{"-"*(len(titlestr)-2)}+')
        print(titlestr)
        print(f'+{"-"*(len(titlestr)-2)}+')
        print(f"Odyssey".ljust(60), "Iliad")
        print("-"*120)
        for i, (otop, itop) in enumerate(zip(ranked_mindwords_odyssey[mindword][:n_top_coocs], ranked_mindwords_iliad[mindword][:n_top_coocs])):
            print(
                f"{i+1}.: {otop[0]}".ljust(20), 
                f"pmi: {otop[1]:.2f}".ljust(15),
                f"c(a,b) {cooccurences_odyssey[(mindword, otop[0])]}".ljust(10),
                f"c(b) {wc_odyssey[otop[0]]}".ljust(10),
                f"{i+1}.: {itop[0]}".ljust(20), 
                f"pmi: {itop[1]:.2f}".ljust(15),
                f"c(a,b) {cooccurences_iliad[(mindword, itop[0])]}".ljust(10),
                f"c(b) {wc_iliad[itop[0]]}",
            )
        print("-"*120)

def pmi(words_freqs, pair_freqs, k=1):
    pmis = {}
    tot = sum(words_freqs.values())
    tot_pairs = sum(pair_freqs.values())
    for pair in pair_freqs:
        P_a = words_freqs[pair[0]]/tot
        P_b = words_freqs[pair[1]]/tot
        P_ab = pair_freqs[pair]/tot_pairs
        pmi = math.log(P_ab**k/(P_a*P_b), 2)
        pmis[pair] = pmi
    return pmis

def get_surroundings_of_mind_words(sents, pos=None):
    mindwords_with_surroundings = defaultdict(list)
    for sentence in sents:
        has_mindwords = set([w['entry'] for w in sentence]) & MINDWORDS
        surroundings=[]
        if len(has_mindwords) > 0:
            for w in sentence:
                try:
                    if not w['entry'] in STOPWORDS and not w['entry'] in MINDWORDS: 
                        if not pos:
                            surroundings.append(w)
                        elif pos==w["POS"]:
                            surroundings.append(w)
                except KeyError:
                    pass
            for key in has_mindwords:
                mindwords_with_surroundings[key].append(surroundings)
    return mindwords_with_surroundings

def morpho_frequencies_of_mindwords(book):
    tree = ET.parse(f'Homer (0012) - {book} (00{BOOKNR[book]}).xml')
    lemmas = get_lemmas_from_xml(tree)
    morphocount = defaultdict(lambda: defaultdict(int))
    for s in lemmas:
        for l in s:
            for m in l['morpho']:
                morphocount[l['entry']][" ".join(m[1:3])] += 1
    mc_mws = {l:mc for l,mc in morphocount.items() if l in MINDWORDS}
    for mw in mc_mws:
        print(f"Morphology variant counts of mindword {mw} in {book}:")
        ranked_morphos = sorted(mc_mws[mw].items(), reverse=True, key=lambda x:x[1])
        for morpho, freq in ranked_morphos:
            print(morpho, freq)
        print("-"*20)
    return morphocount


def main():
    # mind_words_in_iliad = count_occurences_of_mind_words("Iliad")
    # mind_words_in_odyssey = count_occurences_of_mind_words("Odyssey")
    cooccurring_verbs_iliad, p_ab_iliad, p_b_iliad = analyse_embedding_of_mind_words("Iliad")
    cooccurring_verbs_odyssey, p_ab_odyssey, p_b_odyssey = analyse_embedding_of_mind_words("Odyssey")
    compare_mindword_embeddings(cooccurring_verbs_odyssey, cooccurring_verbs_iliad, p_ab_odyssey, p_ab_iliad, p_b_odyssey, p_b_iliad)
    # morphos_mindword_iliad = morpho_frequencies_of_mindwords("Iliad")
    # morphos_mindword_odyssey = morpho_frequencies_of_mindwords("Odyssey")

if __name__=="__main__":
    main()