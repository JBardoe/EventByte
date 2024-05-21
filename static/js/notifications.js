//Send an AJAX request to delete a notification and update the page
function deleteNotification(notificationId){
    $.post("/deleteNotification",
        {"notificationId":notificationId},
        function(data){
            const notification = document.getElementById(""+notificationId);
            notification.remove(); 
            if (document.getElementsByClassName("eventListItem").length == 0){
                document.getElementById("deletedAllNotifications").classList.remove('hidden');
                document.getElementById("deletedAllNotifications").classList.add('eventListItem');
            }
        }
    );
    return false;
}