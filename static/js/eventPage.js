//Send an AJAX post request to cancel an event and reload the page on success
function cancelEvent(){
    $.post("/cancelEvent",
        {"eventId":document.getElementById("eventId").value},
        function(data){
            location.reload();
        }
    );
}

//Send an AJAX post request to uncancel an event and reload the page on success
function uncancelEvent(){
    $.post("/uncancelEvent",
        {"eventId":document.getElementById("eventId").value},
        function(data){
        location.reload();
    }
    );
}

//Send an AJAX post request to cancel a ticket and on success: alert the user and update which buttons are displayed
function cancelTicket(){
    $.post("/cancelTicket",
        {"eventId":document.getElementById("eventId").value, "userId":document.getElementById("userId").value},
        function(data){
            alert("Ticket Removed.")
            document.getElementById("cancelTicket").setAttribute("hidden", true);
            document.getElementById("viewEventTicket").setAttribute("hidden", true);
            document.getElementById("getTicket").removeAttribute("hidden");
        }
    );
}

//Send an AJAX post request to get a ticket and on success: alert the user and update which buttons are displayed
function getTicket(){
    $.post("/getTicket",
        {"eventId":document.getElementById("eventId").value, "userId":document.getElementById("userId").value},
        function(data){
            alert("Ticket Acquired.")
            document.getElementById("getTicket").setAttribute("hidden", true);
            document.getElementById("cancelTicket").removeAttribute("hidden");
            document.getElementById("viewEventTicket").removeAttribute("hidden");
        }
    );
}

//Send an AJAX post request to register attendance and update the page on success
function registerAttendance(){
    $.post("/registerAttendance",
        {"eventId":document.getElementById("eventId").value},
        function(data){
            alert("Attendance registered")
            document.getElementById("attended").remove();
            document.getElementById("attendedMessage").removeAttribute("hidden");
        }
    );
}