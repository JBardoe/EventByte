//Send an AJAX request to toggle a user's notifications 
function toggleNotifications(){
    $.post("/toggleNotifications",
        {},
        function(data){return false;}
    );
}

//Send an AJAX request to reset the database and alert the user on success
function resetDb(){
    $.post("/resetDb",
        {},
        function(data){
            alert("Database has been reset");
            location.reload();
        }
    );
}