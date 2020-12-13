class TextRepo:

    MSG_NO_RES = "Spiacente! Nessun match con le impostazioni correnti (minimo {}% di matching score)."

    MSG_RESPONSE = """
---------------- MATCH #{} --{}--------------
Topic: <a href="{}">{}</a>
{}
Data: {}
    """

    MSG_NOT_A_CMD = (
        "Questo non è un comando! Invia /help per vedere la lista dei comandi."
    )

    MSG_NOT_VALID_INPUT = "Il valore inviato non ha un formato corretto, inserire un numero intero appartenente all'intervallo previsto."
    MSG_NOT_VALID_RANGE = "Il valore inviato non è nell'intervallo previsto [{},{}]."

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
    """
