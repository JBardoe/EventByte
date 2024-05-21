//Open the side navigation menu when the open button is pressed
function openMenu(){
    document.getElementById("menu").style.width = "25%";
    document.getElementById("openMenu").style.fontSize = "0";
    let events = document.getElementsByClassName("eventListItem");
    for(let i = 0; i<events.length;i++){
        events[i].style.width = "65%";
        events[i].style.marginLeft = "30%"
    }
}

//Close the side navigation menu when the close button is pressed
function closeMenu(){
    document.getElementById("menu").style.width = "0";
    document.getElementById("openMenu").style.fontSize = "300%";
    let events = document.getElementsByClassName("eventListItem");
    for(let i = 0; i<events.length;i++){
        events[i].style.width = "90%";
        events[i].style.marginLeft = "5%"
    }
}