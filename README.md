# Power Pizza Bot

Bot Telegram per ricercare gli argomenti trattati negli episodi di [Power Pizza](https://www.spreaker.com/show/power-pizza), il podcast di Nick Lorro e Sio.

## Come funziona

Il bot può essere aggiunto su Telegram ricercando `@PowerPizzaSearchBot` nella barra in alto.

Per trovare in quali episodi si è parlato di un determinato argomento, inviare 

`/s un argomento a piacere`

ad esempio come mostrato nello screenshot a seguire in cui cerco "dark souls"

![search example](https://github.com/daniele2408/powerpizzabot/blob/master/resources/screenshot_search.png?raw=true)

Il bot mostrerà i risultati più simili al testo ricercato, riportando sia il link del topic che il link all'episodio stesso.

## Trattamento dei dati

Esaminando il codice potreste notare che utilizzo i chat_id degli utenti Telegram per mantenere una configurazione utente e per ricavare il numero di utenti che hanno utilizzato il bot. 

Nel fare questo offusco in maniera non reversibile i chat_id, in modo da conservarne solamente un hash per i sopracitati motivi, preservando allo stesso tempo l'identità di chi utilizza il bot.

## 🎵 ...oh valle abbondante 🎵

Il progetto è ovviamente senza scopo di lucro ed è stato realizzato sia per soddisfazione personale che per tributo al podcast 🍕 se volete però contribuire alle modiche spese di hosting del bot potete offrirmi una birra cliccando sul pulsante a seguire.

[![paypal](https://www.paypalobjects.com/en_US/i/btn/btn_donateCC_LG.gif)](https://www.paypal.com/paypalme/heyitsmedaniele)
