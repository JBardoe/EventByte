//Validate whether the password entered matches the confirm and clear the fields if not
function validateRegister(){
    password = document.getElementById("password").value;
    confirmPassword = document.getElementById("confirmPassword").value; 
    if(password != confirmPassword){
        alert("Confirm password needs to match password");
        document.getElementById("password").value = "";
        document.getElementById("confirmPassword").value = "";
        return false;
    }
}