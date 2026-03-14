const navbar = document.querySelector(".navbar");
const heroButtons = document.querySelector(".hero-buttons");

window.addEventListener("scroll", function () {
    if (window.scrollY > 10) {
        navbar.classList.add("scrolled");
    } else {
        navbar.classList.remove("scrolled");
    }

    if (!heroButtons) return;

    const heroButtonsBottom = heroButtons.getBoundingClientRect().bottom;

    if (heroButtonsBottom <= navbar.offsetHeight + 10) {
        navbar.classList.add("show-buttons");
    } else {
        navbar.classList.remove("show-buttons");
    }
});