from flask import Flask, render_template, request, redirect, session, flash, jsonify
from flask_login import login_user, LoginManager, current_user, logout_user, login_required
from werkzeug import security
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import IntegrityError
from datetime import datetime, time
from flask_mail import Mail, Message
from db_schema import db, User, addUser, alertSuperUser, Event, Log, logAction, dbinit, getPastEvents, getUpcomingEvents, deleteNotification, Ticket, newEvent
from barcode import UPCA
from barcode.writer import SVGWriter 
import os

#Initialise and configure the app
app = Flask(__name__)
app.secret_key = "this whole thing is the secret key 1'#]49(^01A6"

app.config['MAIL_SUPPRESS_SEND'] = False
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///eventbyte.sqlite'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

mail = Mail(app)#Make the mail handler

db.init_app(app)#Initialise the database

#Resets the database by removing all the tables then adding them back and filling in the dummy data
def resetDb():
    with app.app_context():
        db.drop_all()
        db.create_all()
        dbinit()

resetDb()#Database is reset when the app is run

#Create and initialise the login manager
login_manager = LoginManager()
login_manager.init_app(app)

#Defines how the login manager gets the current user
@login_manager.user_loader
def load_user(userId):
    return User.query.get(int(userId))

#Defines what happens when an unauthorised user attempts to acces a page that requires them to be logged 
@login_manager.unauthorized_handler
def unauthorized_callback():
    #Redirect to the login screen
    flash("You need to login to access this page!")
    return redirect("/login")

#Redirects the user in case of an error
@app.errorhandler(Exception)
def handleError(e):
    return render_template("error.html", error = e)


#Route to the index
@app.route('/')
def index():
    return redirect("/allEvents")

#Route to the login page
@app.route('/login', methods=['GET', 'POST'])
def login():
    #When a login request is made:
    if request.method == 'POST':
        #Get the from the form and load the user from the database
        password = request.form.get("password")
        user = User.query.filter_by(email = request.form.get("email")).first()
        
        #If there is no user the email is incorrect
        if user == None:
            flash('Incorrect Username or Password!')
            return redirect("/login")
        #If the passwords do not match the password entered is wrong
        elif not security.check_password_hash(user.password, password):
            flash('Incorrect Username or Password!')
        #Otherwise log them in
        else:
            login_user(user)
            logAction(f'{user.fname} {user.lname} logged in.', datetime.now())
            return redirect("/allEvents")

    return render_template("login.html")

#Route to the registration page
@app.route('/register', methods=['GET', 'POST'])
def register():
    #When a register request is made:
    if request.method == 'POST':
        #Get the email and check if a user with that email already exists
        email = request.form.get("email")
        if User.query.filter_by(email = email).all() :
            flash("There is already an account associated with that email.")
            return redirect('/register')
        
        #Otherwise add the new user and send an email verification link
        addUser(request.form.get("fname"), request.form.get("lname"), email, request.form.get("password"), []) #Password is hashed in the method
        login_user(User.query.filter_by(email = email).first())
        sendEmailVerification(email)
        return redirect("/allEvents")

    return render_template("register.html")

#Route to the main events pages
@app.route('/allEvents', methods=['GET', 'POST'])
def allEvents():
    #Check if the page should display past or upcoming events
    past = request.args.get('past') or False 
    if past:
        events = getPastEvents()
    else:
        events = getUpcomingEvents()

    #If the user is verified pass their id
    if current_user.is_authenticated:
        userId = current_user.id 
        pfp = getPfpPath(current_user)
    else:
        userId = -1
        pfp = "/static/images/defaultpfp.jpeg"
    
    #If there is at least 1 event, sort the events array by their start time
    if len(events)>0:
        events.sort(reverse=True, key=(lambda event: event.start))

    return render_template("allEvents.html", loggedIn = current_user.is_authenticated, isSuperUser = (userId == 1), events = events, past = past, pfp=pfp)

#Route to the user events page
@app.route('/myEvents', methods = ['GET', 'POST'])
@login_required
def myEvents(): 
    #Get the events the user is attending and if there is at least 1 sort the list by date and get whether each event is attended 
    events = current_user.getEvents()
    if len(events)>0:
        events.sort(reverse=True, key=(lambda event: event.start))
    
    #Get the ids of the events that have been attended
    attendedTickets = Ticket.query.filter_by(userId = current_user.id, attended = True).all()
    attendedIds = [ticket.eventId for ticket in attendedTickets]

    return render_template("myEvents.html", events = events, isSuperUser = (current_user.id == 1), attendedIds = attendedIds, pfp = getPfpPath(current_user))

#Route to the notifications page
@app.route('/notifications', methods=['GET', 'POST'])
@login_required
def notifications():
    #Get the user's notifications and if there is at least 1 sort the list by date
    notifications = current_user.getNotifications()
    if len(notifications)>0:
        notifications.sort(reverse=True, key=(lambda notification: notification.time))

    return render_template("notifications.html", notifications = notifications, isSuperUser = (current_user.id == 1), pfp = getPfpPath(current_user))

#Route that responds to AJAX requests to delete a notification
@app.route('/deleteNotification', methods = ['GET', 'POST'])
@login_required
def removeNotification():
    #Delete the relevant notification from the database
    deleteNotification(request.form.get('notificationId'))
    return ""

#Route for the page with the log of website actions
@app.route('/situationLog', methods = ['GET', 'POST'])
@login_required
def situationLog():
    #Only allow access to the super user (id is 1)
    if current_user.id != 1:
        flash("Only super users can access this page.")
        return redirect("/allEvents")

    #Get the system log and if there is at least 1 item sort the list by date
    log = Log.query.all() 
    if len(log)>0:
        log.sort(reverse=True, key=(lambda item: item.time))

    return render_template("situationLog.html", log = log, isSuperUser = True, pfp = getPfpPath(current_user))

#Route to the page for any specific event
@app.route('/event', methods = ['GET', 'POST'])
def eventPage():
    #Get the event from the database
    event = Event.query.filter_by(name = request.args.get("event")).first()
    
    #If the user is authenticated: pass their id, whether they have a ticket to the event, and whether their email is verified
    if current_user.is_authenticated:
        userId = current_user.id 
        hasTicket = event.name in current_user.getEventNames()
        emailVerified = 1 if current_user.emailVerified else 0
        if hasTicket:
            attended = Ticket.query.filter_by(eventId = event.id, userId = current_user.id).first().attended
        else:
            attended = False
    #Otherwise set these to some default values
    else:
        userId = -1
        hasTicket = False
        emailVerified = -1
        attended = False
    
    return render_template("event.html", event = event, userId = userId, isPast = event.start < datetime.now(), hasTicket = hasTicket, emailVerified = emailVerified, attended = attended)

#Route that responds to AJAX requests to cancel an event
@app.route('/cancelEvent', methods=['GET', 'POST'])
@login_required
def cancelEvent():
    #Only allow access to the super user
    if current_user.id != 1:
        flash("Only super users can access this page.")
        return redirect("/allEvents")

    #Cancel the event
    Event.query.filter_by(id = request.form.get("eventId")).first().cancel()
    return ""

#Route that responds to AJAX requests to uncancel an event
@app.route('/uncancelEvent', methods=['GET', 'POST'])
@login_required
def uncancelEvent():
    #Only allow access to the super user
    if current_user.id != 1:
        flash("Only super users can access this page.")
        return redirect("/allEvents")

    #Uncancel the event
    Event.query.filter_by(id = request.form.get("eventId")).first().uncancel()
    return ""

#Route that responds to AJAX requests to get a ticket to an event
@app.route('/getTicket', methods = ['GET', 'POST'])
@login_required
def getTicket():
    #Load the user from the database and add the event taken from the database
    user = User.query.filter_by(id = request.form.get("userId")).first()
    user.addEvent(Event.query.filter_by(id = request.form.get("eventId")).first().name)
    return ""

#Route that responds to AJAX requests to cancel a ticket
@app.route('/cancelTicket', methods = ['GET', 'POST'])
@login_required
def cancelTicket():
    #Load the user from the database and remove the event taken from the database
    user = User.query.filter_by(id = request.form.get("userId")).first()
    user.removeEvent(Event.query.filter_by(id = request.form.get("eventId")).first().name)
    return ""

#Route that responds to AJAX requests to register attendance of an event
@app.route('/registerAttendance', methods = ['GET', 'POST'])
@login_required
def registerAttendance():
    ticket = Ticket.query.filter_by(eventId = request.form.get("eventId"), userId = current_user.id).first()
    ticket.isAttended()
    event = Event.query.filter_by(id = request.form.get("eventId")).first()
    current_user.addNotification(f"You attended {event.name}.", datetime.now())
    return ""

#Route to the page to add events
@app.route('/addEvent', methods=['GET', 'POST'])
@login_required
def addEvent():
    #Only allow access to the super user
    if current_user.id != 1:
        flash("Only super users can access this page.")
        return redirect("/allEvents")
    
    #When an add request is made:
    if request.method == 'POST':
        name = request.form.get("newEventName") #Get the name

        #Get the start date and notify if it is invalid (31st of February e.g.)
        try:
            start = datetime(int(request.form.get('year')), int(request.form.get('month')), int(request.form.get('day')), int(request.form.get('startHour')), int(request.form.get('startMinutes')), 0, 0)
        except ValueError:
            flash("Day outside the range for that month")
            return redirect("/addEvent")
        
        #If the event already exists return an issue
        if Event.query.filter_by(name = name).all():
            flash("There is already an event with this name")
        #If the event is in the past return an issue
        elif start < datetime.now():
            flash("Events in the past cannot be added.")
        #Otherwise add the new event
        else:
            newEvent(request.form.get('newEventName'), start, time(int(request.form.get('durationHour')), int(request.form.get('durationMinutes'))), int(request.form.get('capacity')), [])
            return redirect("/allEvents")
    
    return render_template("addEvent.html", isSuperUser = (current_user.id == 1), pfp = getPfpPath(current_user))

#Route to view tickets
@app.route('/viewTicket', methods=['GET', 'POST'])
@login_required
def viewTicket():
    #Find the ticket in the database
    eventId = request.args.get('eventId') or request.form.get("eventId")
    ticket = Ticket.query.filter_by(eventId = eventId).first()
    
    #If the ticket does not exist, return an issue
    if ticket == None:
        flash('You do not have a ticket for this event')
        return redirect('/myEvents')
    
    #Otherwise load the event and generate the barcode 
    event = Event.query.filter_by(id = eventId).first()
    with open("static/images/barcode.svg", "wb") as file1:
        barcodeImage = UPCA(ticket.barcodeNumber, writer=SVGWriter()).write(file1)
    
    return render_template("viewTicket.html", event = event, barcode = "/static/images/barcode.svg")

#Route the page to edit events
@app.route('/editEvent', methods=['GET', 'POST'])
@login_required
def editEvent():
    #Only allow access to the super user
    if current_user.id != 1:
        flash("Only super users can access this page.")
        return redirect("/allEvents")
    

    event = Event.query.filter_by(name = request.args.get('event')).first() #Load the event in its current form from the database

    #When an edit request is made
    if request.method == 'POST':
        #Edit the event details and check whether there was any issue
        success = event.editEventDetails(startYear=request.form.get("year"), startMonth = request.form.get("month"), startDay = request.form.get("day"), startHour = request.form.get("startHour"), startMinute = request.form.get("startMinutes"), durationHour = request.form.get('durationHour'), durationMinute = request.form.get('durationMinutes'), capacity = request.form.get("capacity"))
        
        #If there was no issue return to the event page
        if success == "Success":
            return redirect(f'/event?event={event.name}')
        #Otherwise display the issue
        else:
            flash(success)
    
    return render_template("editEvent.html", event = event, pfp = getPfpPath(current_user))

#Route to the settings page
@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    #When a reset password request is made, send the link and confirm the action
    if request.method == 'POST':
        sendPasswordReset(current_user.id, "settings")
        flash("Reset Link Sent")
    
    return render_template("settings.html", user = current_user, pfp = getPfpPath(current_user))

#Route to respond to requests to change profile pictures
@app.route('/changeProfilePicture', methods = ['GET', 'POST'])
@login_required
def changeProfilePicture():
    #Get the inputted new profile picture and save it
    file = request.files["newpfp"]
    file.save(f"static/images/{current_user.id}.jpeg")
    return redirect("/settings")


#Route to respond to logout requests
@app.route('/logout', methods=['GET', 'POST'])
@login_required
def logout():
    #Log the current user out and return to the login page
    logout_user()
    return redirect('/login')

#Route to respond to AJAX requests to reset the database
@app.route('/resetDb', methods = ['GET', 'POST'])
@login_required
def superUserResetDb():
    #Only allow the super user
    if current_user.id != 1:
        flash("Only super users can access this page.")
        return redirect("/allEvents")
    
    #Reset the database
    resetDb()
    return ""
    
#Route to respond to AJAX requests to turn on/off notifications for a user
@app.route('/toggleNotifications', methods = ['GET', 'POST'])
@login_required
def toggleNotifications():
    #Toggle the user's notifications
    current_user.toggleNotifications()
    return ""
    
#Route to display the change password page (redirected to by emailed link)
@app.route('/changePassword', methods=['GET', 'POST'])
def changePassword():
    #Get the secure version of the email to change the password for
    hashedEmail = request.args.get("user")

    #Redirect away if one was not given
    if not hashedEmail:
        return redirect("/allEvents")

    #When the password change request is made
    if request.method == 'POST':
        #Get the new password from the form
        password = request.form.get("password")

        #Find the user in the database with the correct email
        users = User.query.all()
        user = None
        for userCheck in users:
            if security.check_password_hash(hashedEmail, userCheck.email):
                user = userCheck
                break
        
        #Login the user, set their new password, and redirect to the events page
        login_user(user)
        user.setPassword(request.form.get("password"))
        logAction(f'{user.fname} {user.lname} changed their password.', datetime.now())
        user.addNotification("Changed password", datetime.now())
        return redirect("/allEvents")
        
    return render_template("changePassword.html", email = hashedEmail)

#Route to the reset password page
@app.route('/resetPassword', methods=['GET', 'POST'])
def resetPassword():
    #When the reset password request is made
    if request.method == 'POST':
        #Load the relevant user from the database
        user = User.query.filter_by(email = request.form.get('email')).first()
        
        #If they're not found, the email entered is wrong
        if user == None:
            flash("There is not user attached to that email")
        #Otherwise send the reset link 
        else:
            sendPasswordReset(user.id, 'resetPassword')
            flash("Reset Link Sent")
            return redirect("/login")

    return render_template("resetPassword.html")

#Route to verify email page (redirected to by emailed link)
@app.route('/verifyEmail', methods = ['GET', 'POST'])
def verifyEmail():
    #Get the secure version of the email to change the password for
    email = request.args.get("email")

    #If one is not provided, redirect away
    if not email:
        return redirect("/allEvents")
    
    #Find the user in the database with that email
    users = User.query.all()
    user = None
    for userCheck in users:
        print(userCheck)
        if security.check_password_hash(email, userCheck.email):
            user = userCheck
            break
    
    #Confirm they have verified their email
    user.confirmEmail()

    #Login the user
    login_user(user)
    return redirect("/allEvents")

#Function to send the password reset requests via email
def sendPasswordReset(userId, previousPage):
    #Find the email from the database to send the link to  
    email = [User.query.filter_by(id = userId).first().email]

    #Hash it so it can be securely included in the url (GET request)
    hashedEmail = security.generate_password_hash(email[0])

    #Generate the message
    sender = f"{os.getlogin()}@dcs.warwick.ac.uk"
    message = Message(subject = "Password Reset Request", sender = ("NOREPLY", sender), recipients = email)

    #Generate the link to be included in message
    url = request.base_url.replace(previousPage, '') + f'changePassword?user={hashedEmail}'

    #Set the message contents
    message.html = render_template("resetEmail.html", url = url)

    #Send the email
    mail.send(message)

#Function to send email verification requests by email
def sendEmailVerification(newEmail):
    #Wrap the email in a list to match the Message contructor parameters
    email = [newEmail]

    #Hash it so it can be securely included in the url (GET request)
    hashedEmail = security.generate_password_hash(email[0])

    #Generate the message
    sender = f"{os.getlogin()}@dcs.warwick.ac.uk"
    message = Message(subject = "Verify Your Email", sender = ("NOREPLY", sender), recipients = email)

    #Generate the link to be included in message
    url = request.base_url.replace("register", '') + f'verifyEmail?email={hashedEmail}'

    #Set the message contents
    message.html = render_template("verifyEmail.html", url = url)

    #Send the email
    mail.send(message)

#Returns the path of the current user's profile picture if they have one
def getPfpPath(user):
    if os.path.exists(f"static/images/{user.id}.jpeg"):
        return f"/static/images/{user.id}.jpeg"
    else:
        return "/static/images/defaultpfp.jpeg"