from flask import Flask, session
import dash
from dash import dcc, html, Input, Output, State
import base64
import os
from datetime import datetime, timedelta
import requests
import hashlib
import cv2
import numpy as np

# User management
class UserManagement:
    def __init__(self):
        self.users = {}  # A dictionary to store user information (username: password)

    def create_account(self, username, password):
        if username in self.users:
            return "Username already exists. Please choose a different username."
        self.users[username] = password
        return "Account created successfully. You can now log in."

    def login(self, username, password):
        if username in self.users and self.users[username] == password:
            return "Logged in successfully."
        return "Invalid username or password."

server = Flask(__name__)
app = dash.Dash(__name__, suppress_callback_exceptions=True, server=server)
app.config.suppress_callback_exceptions = True
app.secret_key = b'secret_key'

user_manager = UserManagement()

# A dictionary to keep track of guest users and their download counts
guest_users = {}

# Define the layout
app.layout = html.Div(style={'backgroundColor': '#1E1E1E', 'padding': '20px'}, children=[
    dcc.Link('Login/Sign Up', href='/login', style={'float': 'right', 'color': '#ffffff', 'text-decoration': 'none', 'margin-right': '10px'}),
    dcc.Location(id='url', refresh=False),
    html.H2("Image Processing Dashboard", style={'color': '#ffffff', 'text-align': 'center'}),
    html.Div(id='page-content'),
    dcc.Upload(
        id='upload-image',
        children=html.Button('Upload Image (JPEG or PNG)', style={'color': '#ffffff', 'background-color': '#007BFF'}),
        multiple=False,
    ),
    html.Br(),
    dcc.Loading(id='loading-output', type='default', children=[
        html.Div(id='image-list', style={'display': 'flex', 'flex-wrap': 'wrap'}),
    ]),
    html.Br(),
    dcc.Dropdown(
        id='processed-images-dropdown',
        options=[],
        multi=False,
        placeholder="Select a Processed Image",
        style={'width': '50%'},
    ),
    html.Br(),
    html.Button('Download Processed Image', id='download-button', disabled=True, style={'color': '#ffffff', 'background-color': '#28A745'}),
])

# Callback to display login or signup layout based on the URL
@app.callback(
    Output('page-content', 'children'),
    Output('upload-image', 'style'),
    Output('login-page-content', 'style'),
    Output('image-list', 'style'),
    Output('processed-images-dropdown', 'style'),
    Output('download-button', 'style'),
    Input('url', 'pathname')
)
def toggle_page_content(pathname):
    if pathname == '/login':
        return (
            None,
            {'display': 'none'},
            {'display': 'block'},
            {'display': 'none'},
            {'display': 'none'},
            {}
        )
    elif pathname == '/signup':
        return (
            None,
            {'display': 'none'},
            {'display': 'none'},
            {'display': 'none'},
            {'display': 'none'},
            {}
        )
    else:
        return (
            html.Div([
                dcc.Upload(
                    id='upload-image',
                    children=html.Button('Upload Image (JPEG or PNG)', style={'color': '#ffffff', 'background-color': '#007BFF'}),
                    multiple=False,
                ),
                html.Br(),
                dcc.Loading(id='loading-output', type='default', children=[
                    html.Div(id='image-list', style={'display': 'flex', 'flex-wrap': 'wrap'}),
                ]),
                html.Br(),
                dcc.Dropdown(
                    id='processed-images-dropdown',
                    options=[],
                    multi=False,
                    placeholder="Select a Processed Image",
                    style={'width': '50%'},
                ),
                html.Br(),
                html.Button('Download Processed Image', id='download-button', disabled=True, style={'color': '#ffffff', 'background-color': '#28A745'}),
            ]),
            {'display': 'block'},
            {'display': 'none'},
            {'display': 'none'},
            {'width': '50%'},
            {}
        )

# Callback to update the image list, processed image dropdown, and download button
@app.callback(
    Output('image-list', 'children'),
    Output('processed-images-dropdown', 'options'),
    Output('download-button', 'disabled'),
    Input('upload-image', 'contents'),
    State('upload-image', 'filename'),
    prevent_initial_call=True
)
def update_uploaded_images(contents_list, filename):
    if contents_list is None:
        return [], [], True

    try:
        image_list = []
        processed_image_options = []

        if filename.lower().endswith(('.jpg', '.jpeg', '.png')):
            # Save the uploaded image
            img_data = base64.b64decode(contents_list.split(',')[1])
            img_path = os.path.join('uploaded', filename)
            with open(img_path, 'wb') as img_file:
                img_file.write(img_data)

            # Display the uploaded image
            img_base64 = base64.b64encode(img_data).decode('utf-8')
            image_list.append(html.Img(src=f'data:image/png;base64,{img_base64}', style={'max-width': '300px'}))
            processed_image_options.append({'label': filename, 'value': filename})

        return image_list, processed_image_options, False
    except Exception as e:
        print("Error while handling uploaded images:", str(e))

# Callback to handle processed image download
@app.callback(
    Output('download-button', 'n_clicks'),
    Input('download-button', 'n_clicks'),
    State('processed-images-dropdown', 'value'),
    prevent_initial_call=True
)
def download_processed_image(n_clicks, selected_image):
    if selected_image:
        try:
            # Process And Download the selected image
            api_url = 'http://127.0.0.1:5000/process_and_download'
            response = requests.post(api_url, data={'image_name': selected_image})

            if response.status_code == 200:
                # Load the processed image
                processed_image_data = response.content
                processed_image_np = np.frombuffer(processed_image_data, np.uint8)
                processed_image = cv2.imdecode(processed_image_np, cv2.IMREAD_COLOR)

                # Apply a blur effect to the image
                blurred_image = cv2.GaussianBlur(processed_image, (25, 25), 0)

                # Convert the blurred image to bytes
                blurred_image_bytes = cv2.imencode('.jpg', blurred_image)[1].tobytes()

                # Check if the user is logged in or a guest
                user_is_logged_in = False  # Assume the user is not logged in (modify this based on your login logic)
                if user_is_logged_in:
                    # Save the processed image (in device)
                    processed_image_path = os.path.join('processed', selected_image)
                    with open(processed_image_path, 'wb') as processed_img_file:
                        processed_img_file.write(blurred_image_bytes)
                else:
                    # Guest user limitation: allow up to 15 downloads every 15 minutes
                    guest_username = 'guest'
                    if guest_username not in guest_users:
                        guest_users[guest_username] = {
                            'remaining_downloads': 15,
                            'last_download_time': datetime.now()
                        }
                    else:
                        user_info = guest_users[guest_username]
                        if user_info['remaining_downloads'] > 0:
                            current_time = datetime.now()
                            if (current_time - user_info['last_download_time']) >= timedelta(minutes=15):
                                user_info['remaining_downloads'] = 15
                            else:
                                user_info['remaining_downloads'] -= 1
                                user_info['last_download_time'] = current_time
                        else:
                            print("Guest user has reached the download limit. Please try again later.")

                return None
            else:
                print(f"Error: {response.status_code} - {response.text}")
        except Exception as e:
            print("An error occurred:", str(e))

if __name__ == '__main__':
    app.run_server(debug=True)
