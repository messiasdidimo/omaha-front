from replit import db
import os
import requests
from datetime import datetime
import json


import pandas as pd
from flask import Flask, render_template, request, jsonify
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from replit.object_storage import Client
from markupsafe import Markup

client = Client()

def send_email(name, recipient_email):
  common_symbols_url = os.environ.get('GET_COMMON_SYMBOLS')
  response = requests.get(common_symbols_url)
  my_email = 'mda.learn@gmail.com'
  password = os.environ.get('EMAIL_PASSWORD')

  # Fetch common symbols data from another project's database
  try:
      # Fetch the data using client; assuming 'common_symbols_data' is the key where data is stored
      common_symbols_data = response.json()
      flattened_data = []
      for company_data in common_symbols_data:
          for symbol, metrics in company_data.items():
              flattened_data.append({'symbol': symbol, **metrics})
      # Assuming it returns a list of dictionaries representing each symbol, convert it to a Pandas DataFrame
      common_symbols_df = pd.DataFrame(flattened_data)
      top_symbols_html = common_symbols_df.to_html(index=False)  # Convert to HTML table
  except Exception as e:  # Catching all exceptions to handle both connection and conversion errors
      top_symbols_html = "<p>No common symbols data found for today.</p>"

  # Construct the HTML message
  html_message = f"""
  <html>
  <head></head>
  <body>
      <p>Hi {name},</p>

      <p>Here are the stocks trading for less than their true value that I found today:</p>
      {top_symbols_html.replace('<td>', '<td style="text-align: center;">')}  

      <p>Pick one and start growing your future wealth!</p>

      <p>Oracle of Omaha</p><br>
      <small><i>This is for informational purposes only. For financial advice, consult a professional.</i></small><br>
      <small><i>We are in beta testing, please answer this 3 simple multiple choice <a href="https://forms.gle/5TZuPSrTDgxcpNx1A">questions</a> to help us improve.</i></small><br>
      <small><i>Click <a href="https://oracleofomaha.replit.app/unsubscribe">here</a> to unsubscribe.</i></small>
  </body>
  </html>
  """

  # Construct the message (MIMEMultipart for mixed content)
  message = MIMEMultipart('alternative')  # 'alternative' allows for both text and html
  message['Subject'] = "Oracle of Omaha - check today stocks opportunities!" 
  message['From'] = my_email
  message['To'] = recipient_email

  # Attach the HTML part
  html_part = MIMEText(html_message, 'html')   
  message.attach(html_part)

  # Send the email using smtplib
  with smtplib.SMTP('smtp.gmail.com', 587) as connection:
     connection.starttls()
     connection.login(user=my_email, password=password)
     connection.sendmail(
         from_addr=my_email,
         to_addrs=recipient_email,
         msg=message.as_string()  # Convert to string for sending
     )
    

def update_subscribers_in_json():
  filename = 'subscribers.json'  # The file to save the emails to

  # Fetch subscriber data from Replit DB
  subscribers_data = db["subscribers"]

  # Extract subscribers' names and emails
  subscribers_list = [{"name": value["Name"], "email": key} for key, value in subscribers_data.items()]

  # Convert to JSON formatted string
  content = json.dumps(subscribers_list, indent=4)

  # Now 'content' is a JSON string that can be uploaded
  client.upload_from_text("subscribers.json", content)



def update_unsubscribed_in_json():
  # The key in the replit database for unsubscribed users
  unsubscribed_key = "unsubscribed"

  # Fetch unsubscribed data from Replit DB
  unsubscribed_data = db[unsubscribed_key]

  # Assuming unsubscribed_data is a dictionary with emails as keys, prepare the email list
  email_list = list(unsubscribed_data.keys())  # Extracting email addresses

  # Use json.dumps to convert the list to a JSON formatted string
  content = json.dumps(email_list, indent=4)

  # Use the client to upload this string under the appropriate filename
  client.upload_from_text("unsubscribed.json", content)
  


def send_to_proxy():
  subscribers_url = os.environ.get('POST_SUBSCRIBERS')

  # The 'subscribers.json' file is uploaded to object storage, we need to download it first
  subscribers_json = client.download_as_text("subscribers.json")
  subscribers_data = json.loads(subscribers_json)  # Parse the JSON string into a Python object

  # Make the POST request to add the subscribers
  headers = {'Content-Type': 'application/json'}
  response = requests.post(subscribers_url, json=subscribers_data, headers=headers)

  print("Status Code:", response.status_code, "Response:", response.json())


def flatten_data(data):
  """Flattens nested data structures into a list of dictionaries.
  Args:
      data (list): A list of dictionaries or nested data structures.
  Returns:
      list: A flattened list of dictionaries.
  """
  flattened_data = []
  for company_data in data:
      for symbol, metrics in company_data.items():
          flattened_data.append({'symbol': symbol, **metrics})
  return flattened_data

# ==================== MAIN SCRIPT ====================

# Initialize Flask app
app = Flask(__name__)

# Define route for the index page
@app.route('/')
def index():
  objects = client.list()
  return render_template('index.html')


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'GET':
        return render_template('signup.html')
    elif request.method == 'POST':
        email = request.form.get('email')
        name = request.form.get('name')
        terms_agreement = request.form.get('terms_agreement')
        agreement_status = 'Agreed' if terms_agreement == 'agreed' else 'Not agreed'
        subscription_date = datetime.now().strftime("%Y-%m-%d")
        subscription_time = datetime.now().strftime("%H:%M:%S")

        # Initialize subscribers and unsubscribed if they do not exist in db
        if 'subscribers' not in db.keys():
            db['subscribers'] = {}
        if 'unsubscribed' not in db.keys():
            db['unsubscribed'] = {}

        # Key to access subscribers and unsubscribed users in Replit DB
        subscribers_key = 'subscribers'
        unsubscribed_key = 'unsubscribed'

        # Fetch existing unsubscribed users
        unsubscribed = db.get(unsubscribed_key, {})
        # Check if email is in unsubscribed users and remove it if present
        if email in unsubscribed:
            del unsubscribed[email]
            db[unsubscribed_key] = unsubscribed  # Save updated unsubscribed users

        # Fetch existing subscribers or initialize an empty dictionary
        subscribers = db.get(subscribers_key, {})
        # Check if email is already registered
        if email in subscribers:
            return jsonify({'message': 'Email already registered'}), 200

        # Update subscribers dictionary with new subscriber
        subscribers[email] = {
            'Name': name,
            'Terms Agreement': agreement_status,
            'Subscription Date': subscription_date,
            'Subscription Time': subscription_time
        }

        # Save updated dictionary to Replit DB
        db[subscribers_key] = subscribers

        # Update and upload both subscribers and unsubscribed lists after modifications
        update_subscribers_in_json()

        update_unsubscribed_in_json()

        send_to_proxy()

        # Send a welcome or subscription confirmation email
        send_email(name, email)
        return jsonify({'message': 'Subscription successful!'}), 200


@app.route('/unsubscribe', methods=['GET', 'POST'])
def unsubscribe():
    if request.method == 'GET':
        return render_template('unsubscribe.html')
    elif request.method == 'POST':
        email = request.form.get('email')
        # Define keys for accessing data in Replit DB
        subscribers_key = 'subscribers'
        unsubscribed_key = 'unsubscribed'

        # Fetch existing data
        subscribers = db.get(subscribers_key, {})
        unsubscribed = db.get(unsubscribed_key, {})

        # Get current date and time
        unsubscribe_date = datetime.now().strftime("%Y-%m-%d")
        unsubscribe_time = datetime.now().strftime("%H:%M:%S")

        if email in subscribers:
            # Remove from subscribers
            del subscribers[email]

            # Add to unsubscribed with date and time
            unsubscribed[email] = {
                'Unsubscribe Date': unsubscribe_date,
                'Unsubscribe Time': unsubscribe_time
            }

            # Save the updated data to Replit DB
            db[subscribers_key] = subscribers
            db[unsubscribed_key] = unsubscribed

            # Update and upload both subscribers and unsubscribed lists after modifications
            update_subscribers_in_json()

            update_unsubscribed_in_json()

            send_to_proxy()


            return jsonify({'message': 'You have been unsubscribed'}), 200
        else:
            return jsonify({'message': 'Email not found in subscribers'}), 200


# Define route for the "Stocks" button behavior
@app.route('/stocks')
def pick_stocks():
    # Fetch data from different endpoints
    common_symbols_url = os.environ.get('GET_COMMON_SYMBOLS')
    growth_data_url = os.environ.get('GET_GROWTH_DATA')
    dividends_data_url = os.environ.get('GET_DIVIDENDS_DATA')
    health_data_url = os.environ.get('GET_HEALTH_DATA')
    gnumber_data_url = os.environ.get('GET_GNUMBER_DATA')
    marketcap_data_url = os.environ.get('GET_MARKETCAP_DATA')
    # Fetch data for each endpoint
    common_symbols_response = requests.get(common_symbols_url)
    growth_data_response = requests.get(growth_data_url)
    dividends_data_response = requests.get(dividends_data_url)
    health_data_response = requests.get(health_data_url)
    gnumber_data_response = requests.get(gnumber_data_url)
    marketcap_data_response = requests.get(marketcap_data_url)
    # Process and convert data to HTML tables
    try:
        # common_symbols_data = common_symbols_response.json()
        # flattened_data = []
        # for company_data in common_symbols_data:
        #     for symbol, metrics in company_data.items():
        #         flattened_data.append({'symbol': symbol, **metrics})
        # # Assuming it returns a list of dictionaries representing each symbol, convert it to a Pandas DataFrame
        # common_symbols_df = pd.DataFrame(flattened_data)
        # top_symbols_html = common_symbols_df.to_html(index=False)  # Convert to HTML table
  
        growth_data = growth_data_response.json()
        dividends_data = dividends_data_response.json()
        # health_data = health_data_response.json()
        gnumber_data = gnumber_data_response.json()
        marketcap_data = marketcap_data_response.json()
        print('marketcap_data:', marketcap_data)
        # # Convert data to DataFrames
        
        growth_df = pd.DataFrame(growth_data)
        dividends_df = pd.DataFrame(dividends_data)
        # health_df = pd.DataFrame(health_data)
        gnumber_df = pd.DataFrame(gnumber_data)
        marketcap_df = pd.DataFrame(marketcap_data)
        print('marketcap_df', marketcap_df)
        # # Convert DataFrames to HTML tables
        
        growth_html = growth_df.to_html(index=False)
        dividends_html = dividends_df.to_html(index=False)
        # health_html = health_df.to_html(index=False)
        gnumber_html = gnumber_df.to_html(index=False)
        marketcap_html = marketcap_df.to_html(index=False)
        print('marketcap_html', marketcap_html)
    except Exception as e:
        print('exception')
        top_symbols_html = "<p>No common symbols data found for today.</p>"
        growth_html = "<p>No growth data found for today.</p>"
        dividends_html = "<p>No dividends data found for today.</p>"
        health_html = "<p>No health data found for today.</p>"
        gnumber_html = "<p>No gnumber data found for today.</p>"
        marketcap_html = "<p>No market cap data found for today.</p>"
    return render_template('stocks.html', 
                           # top_symbols_html=Markup(top_symbols_html),
                           growth_html=Markup(growth_html),
                           dividends_html=Markup(dividends_html),
                           # health_html=Markup(health_html),
                           gnumber_html=Markup(gnumber_html),
                           marketcap_html=Markup(marketcap_html)
                          )


# Define route for the "How to Invest like Warren Buffet" button
@app.route('/buffett')
def warren_buffett():
    # Add any desired logic here
    return render_template('buffett.html')

@app.route('/methodology')
def value_investing():
    # Add any desired logic here
    return render_template('methodology.html')

@app.route('/terms')
def terms():
    terms_file_path = 'static/terms.txt'  # Adjust the path as needed
    try:
        with open(terms_file_path, 'r') as file:
            terms_content = file.read()
            # Split the content into paragraphs based on newlines
            terms_paragraphs = terms_content.split('\n\n')
    except FileNotFoundError:
        terms_paragraphs = ["Terms content not found!"]
    return render_template('terms.html', terms_paragraphs=terms_paragraphs)


if __name__ == '__main__':
  app.run(host='0.0.0.0', port=8080, debug=True)