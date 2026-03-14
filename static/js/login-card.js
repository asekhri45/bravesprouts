document.addEventListener("DOMContentLoaded", () => {
    const animationDuration = 1000;
    const loops = 2;

    const loginCard = document.getElementById("login-card");

    if (loginCard) {
        setTimeout(() => {
            loginCard.classList.add("static");
        }, animationDuration * loops);
    }
});