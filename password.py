from werkzeug.security import generate_password_hash

# Password to be hashed
password = 'admin0'

# Generate the hashed password
hashed_password = generate_password_hash(password)

# Print the hashed password
print(hashed_password)
