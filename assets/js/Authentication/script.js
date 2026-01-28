const loginText = document.querySelector(".title-text .login");
const loginForm = document.querySelector("form.login");
const loginBtn = document.querySelector("label.login");
const signupBtn = document.querySelector("label.signup");
const signupLink = document.querySelector("form .signup-link a");
const sliderTab = document.querySelector(".slider-tab");

signupBtn.onclick = (() => {
    loginForm.style.marginLeft = "-50%";
    loginText.style.marginLeft = "-50%";
    sliderTab.style.left = "50%";  // Move slider to the right

    // Change text colors
    loginBtn.style.color = "#000";   // Make login black
    signupBtn.style.color = "#fff";  // Make signup white
});

loginBtn.onclick = (() => {
    loginForm.style.marginLeft = "0%";
    loginText.style.marginLeft = "0%";
    sliderTab.style.left = "0%";  // Move slider to the left

    // Change text colors
    loginBtn.style.color = "#fff";   // Make login white
    signupBtn.style.color = "#000";  // Make signup black
});

signupLink?.addEventListener("click", (e) => {
    e.preventDefault();
    signupBtn.click();
});
