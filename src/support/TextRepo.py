class TextRepo:

    MSG_NO_RES = "Spiacente! Nessun match rilevato."

    MSG_RESPONSE = """
---------------- MATCH #{} --{}--------------
Topic: <a href="{}">{}</a>
{}
Data: {}
    """

    MSG_NOT_A_CMD = (
        "Questo non è un comando! Invia /help per vedere la lista dei comandi."
    )

    MSG_NOT_VALID_INPUT = "Il valore inviato non ha un formato corretto, inserire un numero intero appartenente " \
                          "all'intervallo previsto, eventualmente seguito da una lettera minuscola non accentata."
    MSG_EPISODE_NOT_FOUND = "Non esiste l'episodio numero {}{}!"
    MSG_EPISODE_NOT_FOUND_MISSING_SUBLETTER = "Esistono episodi con numero {}, ma devi specificare la lettera!" \
                                              " Scegli tra {}"
    MSG_SEARCH_EMPTY_INPUT = "Hai inviato il comando senza nessuna parola da ricercare!"
    MSG_TOP_EMPTY_INPUT = "Hai inviato il comando senza nessun numero da impostare!"
    MSG_NOT_VALID_DATE = "Le date immesse non hanno formato corretto - inserire DDMMYY oppure DDMMYY DDMMYY"
    MSG_NOT_VALID_RANGE = "Il valore inviato non è nell'intervallo previsto da {} a {} entrambi inclusi."

    MSG_SAME_VALUE = "Il numero di risultati mostrati è già pari a {}."
    MSG_SET_MIN_SCORE = "Ho impostato {}% come soglia minima di match score."
    MSG_SET_FIRST_N = "D'ora in poi ti mostrerò i primi {} risultati della ricerca."

    MSG_PRINT_CFG = "Top risultati: {}\nSoglia minima: {}%"

    MSG_START = """
Ciao! Sono un bot per ricercare argomenti trattati dal podcast di Sio, Lorro e Nick: Power Pizza!

Il comando `/help` ti mostrerà i comandi disponibili, altrimenti prova direttamente a inviare
`/s Hollow Knight`
oppure qualsiasi altro argomento ti venga in mente.
    """

    MSG_HELP = """
 `/s <testo>`\nper ricercare un argomento tra quelli elencati negli scontrini delle puntate.\n
 `/top <n>`\nper far apparire solo i primi n messaggi nella ricerca.\n
 `/last`\nmostra gli argomenti dell'ultimo episodio raccolto dal bot.\n
 `/get <n>`\nmostra gli argomenti dell'episodio avente il numero richiesto.\n
    """

    MSG_TOT_USERS = "{} utenti hanno usato finora il bot."
    MSG_MOST_COMMON_WORDS = "Le {} parole più frequenti sono:\n\n{}"
    MSG_TOT_EPS = "Al momento sono presenti {} episodi."

    MSG_DAILY_REPORT = "Log giornaliero dal {} al {} (UTC)"

    MSG_MEMO_AMDIN = """
`/dump`\ndumpa tutto\n
`/nu`\nutenti totali\n
`/neps`\ntotale episodi\n
`/ncw $n`\nparole più cercate\n
`/qry $from [$to]`\nlog giornalieri da DDMMYY a oggi, oppure a DDMMYY\n
"""

    MSG_SINGLE_TOPIC = '<a href="{}">{}</a>'