I wanted to try my hand at pulling emotion from text — something that can be used in much bigger 
commercial grade applications, but I wanted to get my foot in the door and try it for myself. This 
compares VADERsentiment (fast rule-based) vs a Hugging Face transformer model side by side through a 
Flask web app with user signup/login and CSRF prevention via Flask sessions. All analysis history 
gets stored in an SQLite database with separate user accounts, and there's a history page showing 
every analysis with pie charts and a speed comparison chart. There's also a helper script 
(vw_sentimentdb.py) that gives you basically a view of all data in the tables. No API keys 
needed — everything runs locally. 


To run it:

git clone https://github.com/NurJohnston/SentimentDashboard.git

cd SentimentDashboard

pip install -r requirements.txt

python app.py
