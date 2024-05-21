from flask_sqlalchemy import SQLAlchemy 
from werkzeug import security
from flask_login import UserMixin
import pickle
from datetime import datetime, date, time

#Create the database
db = SQLAlchemy()

#Table for the users
class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True) #Only the super user will have an id of 1 which discerns them
    fname = db.Column(db.Text()) #First name
    lname = db.Column(db.Text()) #Last name
    email = db.Column(db.Text()) #Email
    password = db.Column(db.Text()) #Password
    events = db.Column(db.PickleType) #List of events they have tickets for 
    doNotifications = db.Column(db.Boolean) #Whether they want notifications
    emailVerified = db.Column(db.Boolean) #Whether they have verified their email
    
    def __init__(self, fname, lname, email, password, events):
        self.fname = fname
        self.lname = lname 
        self.email = email 
        self.password = password
        self.events = pickle.dumps(events) #The events list is pickled so it can be properly stored in the database
        self.doNotifications = True #Notifications default to on
        self.emailVerified = False #Email is not verified until they click the link sent to them 
    
    #Change the user's password
    def setPassword(self, newPassword):
        hashedPassword = security.generate_password_hash(newPassword)
        self.password = hashedPassword
        db.session.commit()
    
    #Return the event rows for the events the user has tickets for
    def getEvents(self):
        #Unpickle the events list
        eventList = pickle.loads(self.events)

        #Get the event rows in the database associated with the names and return this list
        events = []
        for event in eventList:
            events.append(Event.query.filter_by(name = event).first())
        return events

    #Get just the names of the events the user has tickets for
    def getEventNames(self):
        eventList = pickle.loads(self.events)
        return eventList
    
    #Get all the notifications for the user
    def getNotifications(self):
        return Notification.query.filter_by(userId = self.id).all()
    
    #Register that a user has gotten a ticket for an event
    def addEvent(self, event):
        #Find the event in the database
        newEvent = Event.query.filter_by(name = event).first()

        #Add the user to the event's list of attendees checking whether there is space (Technically should always be true as the site does not allow people to select the option unless there's space)
        space = newEvent.addAttendee(self.id) 

        #Generate the ticket checking whether it is possible (again should always be true)
        ticketAvailable = generateTicket(newEvent.id, self.id)

        #As long as there is space and a ticket could be made
        if(space and ticketAvailable):
            #Add the event name to the list of user events
            unpickledEvents = pickle.loads(self.events)
            unpickledEvents.append(event)
            self.events = pickle.dumps(unpickledEvents)

            #Confirm the event was added
            logAction(self.fname+" "+self.lname+" is now attending "+event+".", datetime.now())
            self.addNotification("You got a ticket for "+event, datetime.now())
            return True
        #Otherwise return that the event could not be added
        else:
            return False

    #Unregister the user's planned attendance to an event
    def removeEvent(self, event):
        #Find the event in the database and remove the user from the attendees
        removedEvent = Event.query.filter_by(name = event).first()
        removedEvent.removeAttendee(self.id)

        #Remove the event from the user's list of events
        unpickledEvents = pickle.loads(self.events)
        unpickledEvents.remove(event)
        self.events = pickle.dumps(unpickledEvents)
        logAction(self.fname+" "+self.lname+" is no longer attending "+event+".", datetime.now())
        self.addNotification("You cancelled your ticket for "+event, datetime.now())

        #Delete the ticket from the database
        removedTicket = Ticket.query.filter_by(eventId = removedEvent.id, userId = self.id).first()
        db.session.delete(removedTicket)
        db.session.commit()
        return True
    
    #Add a new notification for a user if they still have them on
    def addNotification(self, notification, time):
        if self.doNotifications:
            newNotification = Notification(notification, time, self.id)
            db.session.add(newNotification)
            db.session.commit()
    
    #Toggle whether the user wants notifications
    def toggleNotifications(self):
        self.doNotifications = not self.doNotifications
        db.session.commit()

    #Confirm that the user has verified their email
    def confirmEmail(self):
        self.emailVerified = True
        self.addNotification("You have confimed your email", datetime.now())
        alertSuperUser(f"{self.fname} {self.lname} verified their email address", datetime.now())
        db.session.commit()
    
#Add a new user
def addUser(fname, lname, email, rawPassword, events):
    #Generate the password hash
    hashedPassword = security.generate_password_hash(rawPassword)

    #Add the new user
    newUser = User(fname, lname, email, hashedPassword, events)
    db.session.add(newUser)
    db.session.commit()
    logAction("A new user has registered: "+fname+" "+lname+".", datetime.now())

#Notify the super user of an activity 
def alertSuperUser(alert, time):
    superUser = User.query.filter_by(id = 1).first() 
    superUser.addNotification(alert, time)

#Table for all the notifications
class Notification(db.Model):
    __tablename__ = 'notifications'
    id = db.Column(db.Integer, primary_key=True)
    notification = db.Column(db.Text()) #Text of the notification
    time = db.Column(db.DateTime) #Time of the event
    userId = db.Column(db.Integer, db.ForeignKey('users.id')) #Id of the associated user
    
    def __init__(self, notification, time, userId):
        self.notification = notification
        self.time = time
        self.userId = userId
    
    #Return the time of the notification in a formatted string list
    def getFormattedDate(self):
        return [str(self.time.hour) + ":" + str(self.time.strftime("%M")), str(self.time.day) + " " + self.time.strftime("%B") + " " + str(self.time.year)]

#Delete a notification from the database
def deleteNotification(notificationId):
    deletedNotification = Notification.query.filter_by(id = notificationId).first()
    db.session.delete(deletedNotification)
    db.session.commit()


#Table for all the events
class Event(db.Model):
    __tablename__ = 'events'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.Text()) #Event name
    start = db.Column(db.DateTime) #Start date and time
    duration = db.Column(db.Time) #Duration
    capacity = db.Column(db.Integer) #Capacity
    active = db.Column(db.PickleType) #Whether the event is still happening (not cancelled)
    warning = db.Column(db.Boolean) #Whether the event is near capacity
    full = db.Column(db.Boolean) #Whether the event is full
    attendees = db.Column(db.PickleType) #List of users attending the event
    
    def __init__(self, name, start, duration, capacity, attendees):
        self.name = name
        self.start = start
        self.duration = duration
        self.capacity = capacity
        self.active = True #Active is automatically set to True as it would be nonsensical for new events that are already cancelled
        self.warning = float(len(attendees)) >= 0.95*(float(capacity)) and len(attendees) < capacity #Check whether the attendees added is cause for warning
        self.full = len(attendees) == capacity #Check whether the number of attendees added fills the capacity
        self.attendees = pickle.dumps(attendees) #The attendees list is pickled to properly be stored in the database
        
        logAction("A new event has been registered: "+name+".", datetime.now())
    
    #Unpickle and return the list of attendees
    def getAttendees(self):
        return pickle.loads(self.attendees)
    
    #Add an attendee
    def addAttendee(self, attendee):
        unpickledAttendees = pickle.loads(self.attendees)#Unpickle the list of attendees
        
        #If the event is full return that they could not be added
        if self.full:
            return False 
        
        #Otherwise add the user to the list
        unpickledAttendees.append(attendee)
        self.attendees = pickle.dumps(unpickledAttendees)
        
        #If the event is now nearing capacity add a warning note
        if float(len(unpickledAttendees)) >= 0.95*(float(self.capacity)) and (not self.warning):
            self.warning = True
            alertSuperUser(self.name+" is nearing capacity.", datetime.now())
        
        #If the event is now full, remove the warning and mark it as full
        if len(unpickledAttendees) == self.capacity:
            self.full = True
            self.warning = False
            alertSuperUser(self.name+" is full.", datetime.now())
        
        db.session.commit()
        return True

    #Remove an attendee
    def removeAttendee(self, attendee):
        unpickledAttendees = pickle.loads(self.attendees)#Unpickle the list of attendees

        #Remove the user from the list
        unpickledAttendees.remove(attendee)
        self.attendees = pickle.dumps(unpickledAttendees)

        #If the event was full, mark that it no longer is
        if self.full:
            self.full = False
            alertSuperUser(self.name+" is no longer full.", datetime.now())
        
        #If the event is now not full but near capacity, add a warning note
        if float(len(unpickledAttendees)) >= 0.95*(float(self.capacity)) and (not self.warning):
            self.warning = True
            alertSuperUser(self.name+" is near capacity.", datetime.now())
        
        #If the event did already have a warning but no longer needs one, remove it
        if float(len(unpickledAttendees)) < 0.95*(float(self.capacity)) and self.warning:
            self.warning = False
            alertSuperUser(self.name+" is no longer near capacity.", datetime.now())
        
        db.session.commit()
        return True
    
    #Return how many places are left at the event
    def getRemainingTickets(self):
        unpickledAttendees = pickle.loads(self.attendees)
        return (self.capacity - len(unpickledAttendees))
        
    #Return the start date and time, formatted neatly as a string
    def getFormattedDate(self):
        return str(self.start.hour) + ":" + str(self.start.strftime("%M")) + " on " + str(self.start.day) + " " + self.start.strftime("%B") + " " + str(self.start.year)
        
    #Return the duration formatted as a string
    def getFormattedDuration(self):
        string = ""

        if self.duration.hour != 0:
            string += str(self.duration.hour) + " hours"
        
        if self.duration.hour != 0 and self.duration.minute != 0:
            string += " and "    
        
        if self.duration.minute != 0:
            string += str(self.duration.strftime("%M")) + " minutes"
            
        return string
    
    #Cancel the event
    def cancel(self):
        #Mark that the event is no longer active
        self.active = False 

        #Notify all the attendees that the event is cancelled
        unpickledAttendees = pickle.loads(self.attendees)
        for attendee in unpickledAttendees:
            user = User.query.filter_by(id=attendee).first()
            user.addNotification("Event Cancellation!\n"+self.name+" was cancelled.", datetime.now())
        logAction(self.name+" has been cancelled.", datetime.now())
    
    #Uncancel the event
    def uncancel(self):
        #Mark that the event is active again
        self.active = True 

        #Notify all the people that had tickets that the event is back on (they are able to use their old tickets)
        unpickledAttendees = pickle.loads(self.attendees)
        for attendee in unpickledAttendees:
            User.query.filter_by(id=attendee).first().addNotification("Event Back On!\n+"+self.name+" has been uncancelled and will go ahead.", datetime.now())
        
        logAction(self.name+" has been uncancelled.", datetime.now())
    
    #Edit the details of an event
    def editEventDetails(self, startYear=None, startMonth = None, startDay = None, startHour = None, startMinute = None, durationHour=None, durationMinute = None, capacity=None):
        #If the start date of time has been altered in any way
        if startYear or startMonth or startDay or startHour or startMinute:
            #Reassign only the date and time components that have a new value
            startYear = int(startYear) if startYear else self.start.year
            startMonth = int(startMonth) if startMonth else self.start.month
            startDay = int(startDay) if startDay else self.start.day 
            startHour = int(startHour) if startHour else self.start.hour 
            startMinute = int(startMinute) if startMinute else self.start.minute

            #Create the new datetime object
            try:
                start = datetime(startYear, startMonth, startDay, startHour, startMinute, 0, 0)
            #If the new date would be invalid (e.g. 31st of February) notify this and do not add the changes
            except ValueError:
                return "Date outside the range for the month"
            
            #If the event would be in the past now, notify this and do not add the changes otherwise change the event start 
            if start > datetime.now():
                self.start = start
                alertSuperUser("The start time of "+self.name+" has been changed to "+self.getFormattedDate(), datetime.now())
            else:
                return "Cannot change start time into past"
        
        #If the duration components have been changed in any way
        if durationHour or durationMinute:
            #Reassign only the component(s) that have been changed and generate the new time object (try catch is not needed as the form does not allow invalid times)
            durationHour = int(durationHour) if durationHour else self.duration.hour
            durationMinute = int(durationMinute) if durationMinute else self.duration.minute 
            duration = time(durationHour, durationMinute)

            #Update the duration
            self.duration = duration 
            alertSuperUser("The duration of "+self.name+" has been changed to "+self.getFormattedDuration(), datetime.now())

        #If the capacity has been changed
        if capacity:
            #Check if the capacity can be changed to that value
            capacity = self.canDecreaseCapacity(int(capacity))

            #If it can, update the capacity
            if capacity:
                self.capacity = int(capacity)
                alertSuperUser("The capacity of "+self.name+" has been changed to "+str(capacity)+" people", datetime.now())
            #Otherwise, notify the change is invalid and do not add the change
            else:
                return "Cannot decrease capacity below current attendants"
            
        db.session.commit()
        return "Success"

    #Check whether the capacity can be changed to the desired number
    def canDecreaseCapacity(self, newCapacity):
        unpickledAttendees = pickle.loads(self.attendees) #Unpickle the list of attendees

        #If the new capacity would be lower than the number of attendants, return that the change cannot be made
        if len(unpickledAttendees) > newCapacity:
            return None 
        #If the change would make it so the event is now full update the event to be full
        elif len(unpickledAttendees) == newCapacity:
            self.full = True
            alertSuperUser(self.name+" is full.", datetime.now())
        #If the change would not make it full but would put it near capacity, add a warning note
        elif float(len(unpickledAttendees)) >= 0.95*(float(self.capacity)):
            self.warning = True
            alertSuperUser(self.name+" is near capacity.", datetime.now())
        
        #Return that the new capacity is valid
        return int(newCapacity)

            
#Add a new event
def newEvent(name, start, duration, capacity, attendees):
    #If there is already an event with the same name do not allow the new event
    if(Event.query.filter_by(name = name).first() != None):
        return False
    #Otherwise add the event
    else:
        newEvent = Event(name, start, duration, capacity, attendees)
        db.session.add(newEvent)
        db.session.commit()
        return True

#Get all the events that started in the past 
def getPastEvents():
    past=[]
    events = Event.query.all()
    for event in events:
        if event.start < datetime.now():
            past.append(event)
    return past

#Get all the events that are yet to start
def getUpcomingEvents():
    upcoming=[]
    events = Event.query.all()
    for event in events:
        if event.start >= datetime.now():
            upcoming.append(event)
    return upcoming

#Table to contain a log of all actions on the website for the super userto view
class Log(db.Model):
    __tablename__ = 'actionlog'
    id = db.Column(db.Integer, primary_key = True)
    action = db.Column(db.Text()) #Text of what happened
    time = db.Column(db.DateTime) #Time the action happened
    
    def __init__(self, action, time):
        self.action = action
        self.time = time
        
    #Return the date and time of the action formatted neatly as a string
    def getFormattedDate(self):
        return [str(self.time.hour) + ":" + str(self.time.strftime("%M")), str(self.time.day) + " " + self.time.strftime("%B") + " " + str(self.time.year)]
         
#Log a new action
def logAction(action, time):
    log = Log(action, time)
    db.session.add(log)
    db.session.commit()

#Table to contain all the tickets
class Ticket(db.Model):
    __tablename__ = 'tickets'
    id = db.Column(db.Integer, primary_key = True) 
    eventId = db.Column(db.Integer, db.ForeignKey('events.id')) #Id of the event the ticket is for
    userId = db.Column(db.Integer, db.ForeignKey('users.id')) #Id of the ticket owner
    barcodeNumber = db.Column(db.Text()) #Barcode number
    attended = db.Column(db.Boolean)
    
    def __init__(self, eventId, userId):
        self.eventId = eventId
        self.userId = userId
        self.attended = False
        #Barcode number is not initialised here as it is based on the ID

    #Register user attendance
    def isAttended(self):
        self.attended = True
        db.session.commit()

#Generate a new ticket and add it to the database
def generateTicket(eventId, userId):
    #If the ticket already exists do not add it (the UI does not allow this method to be called if the user has a ticket for this event anyway)
    existing = Ticket.query.filter_by(eventId = eventId, userId = userId).first()
    if existing != None:
        return False
    
    #Generate the new ticket and add it to the database
    newTicket = Ticket(eventId, userId)
    num = str(newTicket.id)
    db.session.add(newTicket)
    db.session.commit()
    
    #Generate the barcode number for the ticket based on its id 
    ticket = Ticket.query.filter_by(eventId = eventId, userId = userId).first()
    num = str(ticket.id)
    #Pad the number as the UPC-A standard uses 12 digit number strings
    for i in range(len(num), 11):
        num = "0" + num
    #Add the barcode number
    ticket.barcodeNumber = num
    
    return True

#Cancel all the tickets for an event
def cancelTickets(eventId):
    tickets = Ticket.query.filter_by(eventId = eventId).all()
    for ticket in tickets:
        db.session.delete(ticket)
    db.session.commit()

#Initialise the database
def dbinit():
    #Add the superuser
    superUser = User("Jack", "Bardoe", "jack.bardoe@warwick.ac.uk", security.generate_password_hash("Password"), [])
    superUser.emailVerified = True

    db.session.add(superUser)
    

    #Some dummy data to show off the functionality of the website
    exampleUsers = [
        User("Andrew", "Hague", "A.Hague@email.ac.uk", security.generate_password_hash("Password"), []),
        User("Alexander", "Dixon", "Alexander.Dixon@email.ac.uk", security.generate_password_hash("Password"), []),
        User("Long", "Tran-Thang", "Long.Tran-Thanh@email.ac.uk", security.generate_password_hash("Password"), []),
        User("Yulia", "Timofeeva", "Y.Timofeeva@email.ac.uk", security.generate_password_hash("Password"), [])
    ]  
    
    db.session.add_all(exampleUsers)

    newEvent("CSS Talk", datetime(2024, 2, 16, 18), time(2, 0, 0, 0), 2, [])
    newEvent("Flask Workshop", datetime(2024, 2, 20, 15, 30), time(0, 30, 0, 0), 20, [])
    newEvent("JavaScript Seminar", datetime(2024, 2, 10, 12, 25), time(1, 0, 0, 0), 40, [])
    newEvent("SQL Lecture", datetime(2024, 5, 20, 20, 45), time(6, 0, 0, 0), 20, [])
    newEvent("jQuery Talk", datetime(2024, 3, 21, 16, 30), time(1, 0, 0, 0), 20, [])
    newEvent("Creating Dummy Data 101", datetime(2024, 8, 18, 12, 00), time(2, 20, 0, 0), 1, [])
    
    exampleUser = User.query.filter_by(id = 1).first()
    exampleUser.addEvent("CSS Talk")
    exampleUser.addEvent("SQL Lecture")
    exampleUser.addEvent("jQuery Talk")
    
    exampleUser = User.query.filter_by(id = 2).first()
    exampleUser.emailVerified = True
    exampleUser.addEvent("CSS Talk")
    exampleUser.addEvent("SQL Lecture")
    
    Event.query.filter_by(id = 5).first().cancel()
    
    db.session.commit()

def test():
    user = User.query.filter_by(id = 1).first()

    qry = text("SELECT * FROM users WHERE id == :id")
    qry = qry.bindparams(id = 1)
    user1 = db.session.execute(qry).fetchall().first()

    qry1 = "SELECT * FROM users WHERE id == :id"
    param = {"id":1}
    user2 = db.session.execute(qry, params).fetchall().first()
    