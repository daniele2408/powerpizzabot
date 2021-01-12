# Power Pizza Bot

Bot Telegram per ricercare gli argomenti trattati negli episodi di [Power Pizza](https://www.spreaker.com/show/power-pizza), il podcast di Nick Lorro e Sio.

## Come funziona

Il bot può essere aggiunto su Telegram ricercando `@PowerPizzaSearchBot` nella barra in alto.

Per trovare in quali episodi si è parlato di un determinato argomento, inviare 

`/s un argomento a piacere`

ad esempio come mostrato nello screenshot a seguire in cui cerco "dark souls"

![alt text](https://github.com/daniele2408/powerpizzabot/blob/master/screenshot_search.png?raw=true)

Il bot mostrerà tutti i risultati abbastanza simili al testo ricercato, riportando sia il link del topic che il link all'episodio stesso.

## Trattamento dei dati

Esaminando il codice potreste notare che utilizzo i chat_id degli utenti Telegram per mantenere una configurazione utente e per ricavare il numero di utenti che hanno utilizzato il bot. 

Nel fare questo offusco in maniera non reversibile i chat_id, in modo da conservarne solamente un hash per i sopracitati motivi preservando allo stesso tempo l'identità di chi utilizza il bot.

## 🎵 Toss a coin to your Witcher 🎵

Il progetto è totalmente senza scopo di lucro ed è stato realizzato sia per soddisfazione personale che per tributo al podcast 🍕 se volete però contribuire alle comunque modiche spese di hosting del bot potete offrirmi una birra cliccando sul bottoncino a seguire!

<!-- Sample of code generated --> 
<form action="https://www.paypal.com/paypalme/heyitsmedaniele" method="post" target="_top">
<input type="hidden" name="cmd" value="_s-xclick">
<input type="hidden" name="hosted_button_id" value="RGQ8NSYPA59FL">
<input type="image" src="https://www.paypalobjects.com/en_US/i/btn/btn_donateCC_LG.gif" border="0" name="submit" alt="PayPal - The safer, easier way to pay online!">
<img alt="" border="0" src="https://www.paypalobjects.com/pt_BR/i/scr/pixel.gif" width="1" height="1">
</form>