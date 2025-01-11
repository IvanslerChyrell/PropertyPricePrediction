import joblib
import mariadb
import pandas as pd
from flask import Flask, render_template, redirect, url_for, flash, request, session
import mysql.connector
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
app = Flask(__name__)

# Initialize the Flask appi
app = Flask(__name__)

# Load pre-trained model and encoders
linear_reg_model = joblib.load('18nov/linear_model.pkl')
le_location = joblib.load('18nov/location_encoder.pkl')
le_property_type = joblib.load('18nov/property_type_supergroup_encoder.pkl')
le_furnishing = joblib.load('18nov/furnishing_encoder.pkl')
le_size_type = joblib.load('18nov/size_type_encoder.pkl')

# Retrieve location and other options for form dropdowns
location_names = list(le_location.classes_)
property_type_options = list(le_property_type.classes_)
furnishing_options = list(le_furnishing.classes_)
size_type_options = list(le_size_type.classes_)


app.secret_key = 'your_secret_key'  # Secret key for flash messages

# Database connection function
def get_db_connection():
    conn = mysql.connector.connect(
        host='localhost',
        user='root',  # Change if necessary
        password='',  # Your database password
        database='property_prediction'  # Ensure the database exists
    )
    return conn

# Route for the sign-up form
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        # Retrieve data from the form
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        phone = request.form['phone']
        address = request.form['address']
        birthdate = request.form['birthdate']

        # Check if passwords match
        if password != confirm_password:
            flash("Passwords do not match!")
            return redirect(url_for('signup'))

        # Hash the password
        hashed_password = generate_password_hash(password)

        # Insert data into the database
        conn = get_db_connection()
        cursor = conn.cursor()

        # Check if the email already exists
        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()

        if user:
            flash("Email is already registered. Please use a different email.")
            return redirect(url_for('signup'))

        # Insert user data into the 'users' table
        cursor.execute(
            "INSERT INTO users (name, email, password, phone, address, birthdate) VALUES (%s, %s, %s, %s, %s, %s)",
            (name, email, hashed_password, phone, address, birthdate)
        )
        conn.commit()

        # Get the user_id of the newly inserted user (you can also use cursor.lastrowid to fetch the last inserted id)
        user_id = cursor.lastrowid

        # Log the user's sign-up activity with the updated message
        activity_details = f"New user {name}({user_id}) has registered."
        log_user_activity(user_id, 'Signup', activity_details)

        cursor.close()
        conn.close()

        # After successful signup, render success message page
        flash("Signup successful! Please log in.")
        return render_template('signup_success.html')  # Show success page with a link to login

    return render_template('signup.html')  # Render the signup.html file from templates folder

# Function to log user activity
def log_user_activity(user_id, activity_type, activity_details=''):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO user_activity (user_id, activity_type, activity_details) VALUES (%s, %s, %s)",
        (user_id, activity_type, activity_details)
    )
    conn.commit()
    cursor.close()
    conn.close()


# Route for login page
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        # Check the database for the user with the provided email
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if user and check_password_hash(user['password'], password):  # Validate password
            # Store user data in session after successful login
            session['user_id'] = user['id']  # Store user ID in session
            session['user_name'] = user['name']  # Store user name in session
            session['user_role'] = user['role']  # Store user role in session

            # Log the login activity with user id and name
            activity_details = f"User {user['name']}({user['id']}) has logged in."
            log_user_activity(user['id'], 'Login', activity_details)

            # Check if the user is an admin
            if user['role'] == 'admin':
                return redirect(url_for('admin_dashboard'))  # Redirect to admin dashboard
            else:
                return redirect(url_for('dashboard'))  # Redirect to user dashboard
        else:
            flash("Invalid email or password. Please try again.")
            return redirect(url_for('login'))  # Redirect back to login if credentials are incorrect

    return render_template('login.html')  # Render login page

# Route for the index (home) page
@app.route('/')
def index():
    return render_template('index.html')  # Render index.html as the home page

@app.route('/dashboard')
def dashboard():
    # Check if user is logged in
    if 'user_id' not in session:
        flash("You need to log in first.")
        return redirect(url_for('login'))  # Redirect to login if not logged in

    # Get the user_id and user_name from session
    user_id = session['user_id']
    user_name = session['user_name']

    # Establish a new connection and cursor
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Fetch unread notifications for the user
    cursor.execute("SELECT * FROM notifications WHERE user_id = %s AND is_read = 0", (user_id,))
    notifications = cursor.fetchall()  # Fetch all unread notifications
    unread_count = len(notifications)  # Count unread notifications

    try:
        # Load the house listing data from CSV
        house_data = pd.read_csv(r'C:\Users\kucul\PycharmProjects\Propertylastupdated\18nov\data_kaggle.csv')
        house_list = house_data[['Location', 'Price']].to_dict(orient='records')
    except FileNotFoundError:
        house_list = []

    # Pagination logic
    houses_per_page = 9  # Show 9 houses per page
    page = request.args.get('page', 1, type=int)  # Default to page 1
    start = (page - 1) * houses_per_page
    end = start + houses_per_page
    houses_to_display = house_list[start:end]  # Slice the list for the current page

    # Calculate total pages
    total_pages = (len(house_list) // houses_per_page) + (1 if len(house_list) % houses_per_page > 0 else 0)

    # Calculate the global index for each property
    global_index_start = (page - 1) * houses_per_page + 1

    # Close the database connection after use
    cursor.close()
    conn.close()

    # Render the house listing page and pass the paginated data, along with notifications
    return render_template('dashboard.html', houses=houses_to_display, page=page,
                           total_pages=total_pages, user_name=user_name, global_index_start=global_index_start,
                           notifications=notifications, unread_count=unread_count)

@app.route('/mark_as_read/<int:notification_id>', methods=['POST'])
def mark_as_read(notification_id):
    # Check if the user is logged in
    if 'user_id' not in session:
        return redirect(url_for('login'))

    # Get the user ID from the session
    user_id = session['user_id']

    # Connect to the database
    conn = get_db_connection()
    cursor = conn.cursor()

    # Update the notification status to "read" (is_read = 1) for the specific notification
    cursor.execute("""
        UPDATE notifications 
        SET is_read = 1 
        WHERE id = %s AND user_id = %s
    """, (notification_id, user_id))

    # Commit the transaction
    conn.commit()

    # Close the connection
    cursor.close()
    conn.close()

    # Redirect back to the dashboard or any page after updating
    return redirect(url_for('dashboard'))

@app.route('/setting', methods=['GET', 'POST'])
def settings():
    if 'user_id' not in session:
        flash("You must be logged in to access settings.", "error")
        return redirect(url_for('login'))  # Redirect to login if user is not logged in

    user_id = session['user_id']

    # Fetch user details from the users table using mysql.connector
    conn = get_db_connection()  # Create a new database connection
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
        user = cursor.fetchone()  # Fetch user details
        if not user:
            flash("User not found.", "error")
            return redirect(url_for('login'))  # Redirect to login if user does not exist
    except mysql.connector.Error as e:
        flash(f"Database error: {e}", "error")
        conn.close()
        return redirect(url_for('login'))

    if request.method == 'POST':
        current_password = request.form.get('currentPassword')

        # Check if current password matches the one in the database
        if user and check_password_hash(user['password'], current_password):

            # Update email
            if 'newEmail' in request.form:
                new_email = request.form.get('newEmail')
                if validate_email(new_email):  # Ensure valid email format
                    cursor.execute("UPDATE users SET email = %s WHERE id = %s", (new_email, user_id))
                    conn.commit()  # Commit changes to the database
                    flash("Email updated successfully!", "success")
                else:
                    flash("Invalid email format.", "error")

            # Update name
            if 'newName' in request.form:
                new_name = request.form.get('newName')
                if new_name.strip():  # Ensure non-empty name
                    cursor.execute("UPDATE users SET name = %s WHERE id = %s", (new_name, user_id))
                    conn.commit()  # Commit changes to the database
                    flash("Name updated successfully!", "success")
                else:
                    flash("Name cannot be empty.", "error")

            # Update password
            if 'newPassword' in request.form and 'confirmNewPassword' in request.form:
                new_password = request.form.get('newPassword')
                confirm_password = request.form.get('confirmNewPassword')

                if new_password == confirm_password:
                    new_password_hashed = generate_password_hash(new_password)
                    cursor.execute("UPDATE users SET password = %s WHERE id = %s", (new_password_hashed, user_id))
                    conn.commit()  # Commit changes to the database
                    flash("Password updated successfully!", "success")
                else:
                    flash("New passwords do not match!", "error")
        else:
            flash("Incorrect current password!", "error")

    conn.close()  # Close the database connection

    return render_template('setting.html', user=user)

# A simple email validation function
def validate_email(email):
    # Simple regex to check if the email format is valid
    import re
    email_regex = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
    return re.match(email_regex, email) is not None

@app.route('/feedback', methods=['GET', 'POST'])
def feedback():
    if request.method == 'POST':
        # Get form data
        name = request.form['name']
        email = request.form['email']
        phone = request.form['phone']
        rating = request.form['rating']
        comments = request.form['comments']

        # Get the user_id from the session (assuming the user is logged in)
        user_id = session.get('user_id')  # Make sure you have a valid session with user_id
        if not user_id:
            flash("You must be logged in to submit feedback", 'error')
            return redirect(url_for('login'))  # Redirect to the login page if user is not logged in

        # Insert the feedback into the feedbacks table
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO feedbacks (user_id, name, email, phone, rating, comments)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (user_id, name, email, phone, rating, comments))
            conn.commit()
            cursor.close()
            conn.close()

            # Activity log details
            user_name = session.get('user_name')  # Assuming the user's name is stored in session
            activity_type = "feedback"
            activity_details = f"User {user_name} ({user_id}) has submitted feedback."

            log_user_activity(user_id, activity_type, activity_details)

            flash('Feedback submitted successfully!', 'success')
            return redirect(url_for('feedback'))  # Redirect back to the feedback page

        except mariadb.Error as e:
            flash(f"Error submitting feedback: {e}", 'error')  # Flash error message
            return redirect(url_for('feedback'))

    return render_template('feedback.html')


# -----------------------------------PREDICTION SECTION-----------------------------------------------------------------

@app.route('/prediction')
def prediction():
    return render_template('prediction.html', locations=location_names,
                           property_types=property_type_options,
                           furnishing_options=furnishing_options,
                           size_types=size_type_options)

@app.route('/predict', methods=['POST'])
def predict():
    if 'user_id' not in session:
        flash("You need to log in first.")
        return redirect(url_for('login'))

    # Retrieve the input data from the form
    location = request.form['Location']
    property_type = request.form['Property Type Supergroup']
    size_type = request.form['SizeType']
    size_value = float(request.form['SizeValue'])
    rooms = float(request.form['Rooms'])
    bathrooms = float(request.form['Bathrooms'])
    car_parks = float(request.form['Car Parks'])
    furnishing = request.form['Furnishing']

    # Encode categorical features using the pre-trained label encoders
    location_encoded = le_location.transform([location])[0]
    property_type_encoded = le_property_type.transform([property_type])[0]
    furnishing_encoded = le_furnishing.transform([furnishing])[0]
    size_type_encoded = le_size_type.transform([size_type])[0]

    # Ensure the feature order matches the training order exactly
    features = pd.DataFrame([[location_encoded, property_type_encoded, size_value, rooms, bathrooms, car_parks, furnishing_encoded, size_type_encoded]],
                            columns=['Location', 'Rooms', 'Bathrooms', 'Car Parks', 'Furnishing', 'SizeType', 'SizeValue', 'Property Type Supergroup'])

    # Predict the price using the model
    try:
        prediction = linear_reg_model.predict(features)[0]
    except ValueError as e:
        print(f"Error in prediction: {e}")
        return "Prediction failed due to feature mismatch."

        # Log the user's activity in the database
    user_id = session['user_id']
    user_name = session['user_name']
    activity_type = "Prediction"
    activity_details = f"User {user_name}({user_id}) has made a predicted price for property at {location} with {rooms} rooms, {bathrooms} bathrooms, and {car_parks} car parks."

    log_user_activity(user_id, activity_type, activity_details)

    # Store the prediction temporarily in the session
    session['temp_prediction'] = {
        'location': location,
        'property_type': property_type,
        'size_type': size_type,
        'size_value': size_value,
        'rooms': rooms,
        'bathrooms': bathrooms,
        'car_parks': car_parks,
        'furnishing': furnishing,
        'prediction': prediction
    }

    # Render the result page with the prediction
    return render_template('result.html', prediction=prediction)

@app.route('/save_prediction')
def save_prediction():
    # Retrieve the prediction data from the session
    prediction_data = session.get('temp_prediction')

    # Log the user's activity in the database
    user_id = session['user_id']
    user_name = session['user_name']
    activity_type = "save prediction"
    activity_details = f"User {user_name}({user_id}) has saved a prediction"

    log_user_activity(user_id, activity_type, activity_details)
    if not prediction_data:
        flash("No prediction data to save.")
        return redirect(url_for('prediction'))  # Redirect to the prediction form

    # Get the user ID from the session
    user_id = session['user_id']

    # Save the prediction to the database
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO predictions 
        (user_id, location, property_type_supergroup, size_type, size_value, rooms, bathrooms, car_parks, furnishing, predicted_price, timestamp) 
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
        """,
        (user_id, prediction_data['location'], prediction_data['property_type'], prediction_data['size_type'],
         prediction_data['size_value'], prediction_data['rooms'], prediction_data['bathrooms'], prediction_data['car_parks'],
         prediction_data['furnishing'], prediction_data['prediction'])
    )
    conn.commit()

    cursor.close()
    conn.close()

    # Clear the temporary prediction data from session
    session.pop('temp_prediction', None)

    flash("Prediction saved successfully!")
    return redirect(url_for('prediction'))  # Redirect to the prediction form

@app.route('/Sprediction')
def Sprediction():
    if 'user_id' not in session:
        flash("You need to log in first.")
        return redirect(url_for('login'))  # Redirect to login if not logged in

    # Get the user ID from the session
    user_id = session['user_id']

    try:
        # Retrieve the saved predictions from the database for this user
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT id, location, predicted_price, timestamp, rooms, bathrooms, car_parks, 
                   property_type_supergroup, size_value, size_type, furnishing
            FROM predictions
            WHERE user_id = %s
            ORDER BY timestamp DESC
        """, (user_id,))
        saved_predictions = cursor.fetchall()  # Fetch all saved predictions for the user

        cursor.close()
        conn.close()
    except Exception as e:
        flash("An error occurred while fetching the saved predictions.")
        print(f"Error: {e}")
        return redirect(url_for('dashboard'))  # Redirect to the dashboard or any error page

    # Pass the saved predictions to the template to display
    return render_template('Sprediction.html', saved_predictions=saved_predictions)

@app.route('/go_back_to_form')
def go_back_to_form():
    # Clear the temporary prediction data from the session
    session.pop('temp_prediction', None)

    flash("Prediction discarded.")
    return redirect(url_for('prediction'))  # Redirect to the prediction form



@app.route('/delete_prediction/<string:location>', methods=['POST'])
def delete_prediction(location):
    # Ensure the user is logged in
    if 'user_id' not in session:
        flash('You need to log in first!', 'danger')
        return redirect(url_for('login'))

    # Get the user_id from the session
    user_id = session['user_id']

    connection = get_db_connection()
    cursor = connection.cursor()

    try:
        # Delete the prediction based on location and user_id
        delete_query = "DELETE FROM predictions WHERE location = %s AND user_id = %s"
        cursor.execute(delete_query, (location, user_id))  # Use the user_id from the session

        connection.commit()

        # Flash a success message
        flash(f'Prediction for location {location} deleted successfully!', 'success')

        # Log the user's activity in the database
        user_id = session['user_id']
        user_name = session['user_name']
        activity_type = "delete prediction"
        activity_details = f"User {user_name}({user_id}) has delete a prediction"

        log_user_activity(user_id, activity_type, activity_details)
    except Exception as e:
        connection.rollback()
        flash(f'An error occurred: {e}', 'danger')

    finally:
        cursor.close()
        connection.close()

    # Fetch the updated list of saved predictions
    connection = get_db_connection()
    cursor = connection.cursor()
    fetch_query = "SELECT * FROM predictions WHERE user_id = %s"
    cursor.execute(fetch_query, (user_id,))
    saved_predictions = cursor.fetchall()

    cursor.close()
    connection.close()

    # Return the updated saved predictions to the template
    return render_template('Sprediction.html', saved_predictions=saved_predictions)


# --------------------------------------------ADMIN SECTION ---------------------------------------------------------

@app.route('/admin_dashboard')
def admin_dashboard():
    # Get a connection to the database
    conn = get_db_connection()

    total_users = 0  # Safe initialization to avoid UnboundLocalError
    active_users = 0  # Initialize active_users with a default value
    recent_activities = []  # Set a default value for recent_activities

    try:
        # Initialize cursor
        cursor = conn.cursor(dictionary=True)

        # Correct the query to use the 'id' column instead of 'user_id'
        cursor.execute("SELECT COUNT(id) AS total_users FROM users")
        total_users_result = cursor.fetchone()
        print(f"Total Users Query Result: {total_users_result}")  # Debugging print
        if total_users_result:
            total_users = total_users_result['total_users']
        else:
            print("No users found in the 'users' table.")  # If no users found

            # Debugging: Print the current date and 30 days ago
            cursor.execute("SELECT NOW(), DATE_SUB(NOW(), INTERVAL 30 DAY);")
            now, thirty_days_ago = cursor.fetchone()
            print(f"Current Date: {now}, 30 Days Ago: {thirty_days_ago}")

            # Debugging current time and activity in the last 30 days
            cursor.execute("SELECT NOW();")
            now = cursor.fetchone()[0]
            print(f"Current Date and Time: {now}")

            cursor.execute("""
                SELECT user_id, timestamp 
                FROM user_activity 
                WHERE timestamp > DATE_SUB(NOW(), INTERVAL 30 DAY)
                LIMIT 5;
            """)
            activity_result = cursor.fetchall()
            print("Activity in the Last 30 Days:")
            for row in activity_result:
                print(f"User ID: {row[0]}, Timestamp: {row[1]}")

            # Now query to count distinct active users
            cursor.execute("""
                SELECT COUNT(DISTINCT user_id) AS active_users
                FROM user_activity
                WHERE timestamp > DATE_SUB(NOW(), INTERVAL 30 DAY)
            """)
            active_users_result = cursor.fetchone()
            print(f"Active Users Query Result: {active_users_result}")

            if active_users_result:
                active_users = active_users_result[0]
                print(f"Active Users: {active_users}")
            else:
                print("No active users found in the past 30 days.")

        # Query to get the most recent 5 activities from the user_activity table
        cursor.execute("SELECT activity_details, timestamp FROM user_activity ORDER BY timestamp DESC LIMIT 5")
        recent_activities = cursor.fetchall()
        print(f"Recent Activities Query Result: {recent_activities}")  # Debugging print
        if not recent_activities:
            print("No recent activities found in 'user_activity' table.")  # If no activities found

        # Close the cursor
        cursor.close()
    except Exception as e:
        print(f"Error: {e}")  # Log the error for debugging purposes
    finally:
        # Ensure the connection is closed in the end
        conn.close()

    # Get the admin's name from the session or set a default
    admin_name = session.get('user_name', 'Admin')

    # Render the dashboard with the total users and recent activities
    return render_template(
        'admin_dashboard.html',
        total_users=total_users,
        active_users=active_users,
        recent_activities=recent_activities,
        admin_name=admin_name
    )


@app.route('/admin/users')
def admin_users():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Query to get all users
    cursor.execute("SELECT id, name, email, phone, created_at FROM users")
    users = cursor.fetchall()

    cursor.close()
    conn.close()

    # Pass the fetched users to the 'admin_users.html' template
    return render_template('admin_users.html', users=users)


@app.route('/admin/users/edit/<int:id>', methods=['GET', 'POST'])
def edit_user(id):
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM users WHERE id = %s", [id])
    user = cur.fetchone()

    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        phone = request.form['phone']

        # Update the user information
        cur.execute("""
            UPDATE users SET name = %s, email = %s, phone = %s WHERE id = %s
        """, (name, email, phone, id))
        mysql.connection.commit()
        flash('User updated successfully!', 'success')
        return redirect(url_for('user_management'))

    return render_template('edit_user.html', user=user)

# Route to delete user
@app.route('/admin/users/delete/<int:id>', methods=['POST'])
def delete_user(id):
    try:
        # Connect to the database
        conn = get_db_connection()
        cursor = conn.cursor()

        # First, delete any dependent records in the user_activity table
        cursor.execute("DELETE FROM user_activity WHERE user_id = %s", (id,))

        # Now, delete the user from the users table
        cursor.execute("DELETE FROM users WHERE id = %s", (id,))

        # Commit the changes and close the connection
        conn.commit()

        flash('User deleted successfully!', 'success')
        return redirect('/admin/users')

    except mysql.connector.Error as e:
        flash(f'Error deleting user: {e}', 'error')
        return redirect('/admin/users')


@app.route('/admin/feedback', methods=['GET'])
def admin_feedback():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)  # Use 'dictionary=True' to get results as dictionaries

        cursor.execute('SELECT id, user_id, name, email, phone, rating, comments, created_at FROM feedbacks')
        feedbacks = cursor.fetchall()  # Fetch all results as a list of dictionaries

        cursor.close()
        conn.close()

        return render_template('admin_feedback.html', feedbacks=feedbacks)
    except mysql.connector.Error as e:
        flash(f"Error retrieving feedback: {e}", 'error')
        return redirect(url_for('admin_feedback'))  # Use the correct route name

@app.route('/admin/read_feedback/<int:feedback_id>', methods=['GET'])
def read_feedback(feedback_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Step 1: Fetch the user_id from the feedbacks table
        cursor.execute("SELECT user_id FROM feedbacks WHERE id = %s", (feedback_id,))
        feedback = cursor.fetchone()

        if not feedback:
            flash("Feedback not found", 'error')
            return redirect('/admin/feedback')

        user_id = feedback[0]  # Extract user_id from the first element of the tuple

        # Debugging: Output the user_id to the console
        print(f"User ID: {user_id}")

        # Step 2: Define the message
        message = "Your feedback has been read by the admin."

        # Debugging: Output the message to the console
        print(f"Notification Message: {message}")

        # Step 3: Insert the notification into the notifications table
        cursor.execute(
            "INSERT INTO notifications (user_id, message, is_read, created_at) VALUES (%s, %s, %s, NOW())",
            (user_id, message, 0)  # is_read = 0 (unread)
        )

        # Commit the changes to the database
        conn.commit()

        flash("Feedback marked as read and notification sent to user.", 'success')
        return redirect('/admin/feedback')

    except Exception as e:
        conn.rollback()
        flash(f"Error: {e}", 'error')
        print(f"Exception: {e}")  # Debug message
        return redirect('/admin/feedback')

    finally:
        cursor.close()
        conn.close()



@app.route('/admin/delete_feedback/<string:comment>', methods=['GET'])
def delete_feedback(comment):
    try:
        # Connect to the database
        conn = get_db_connection()
        cursor = conn.cursor()

        # Delete the feedback from the database using the comment (or other identifier like ID if needed)
        cursor.execute("DELETE FROM feedbacks WHERE comments = %s", (comment,))
        conn.commit()  # Commit the deletion

        # Close the cursor and the connection
        cursor.close()
        conn.close()

        flash('Feedback deleted successfully!', 'success')  # Flash message for success
    except mysql.connector.Error as e:
        flash(f'Error deleting feedback: {e}', 'error')  # Flash message for error

    return redirect(url_for('admin_feedback'))  # Redirect back to the feedback page


# Route to log out
@app.route('/logout')
def logout():
    # Remove user session data
    session.pop('user_id', None)
    session.pop('user_name', None)
    flash("You have been logged out.")
    return redirect(url_for('login'))  # Redirect to login page

if __name__ == '__main__':
    app.run(debug=True)
