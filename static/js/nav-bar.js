const navbar = document.querySelector(".navbar");
const heroButtons = document.querySelector(".hero-buttons");

let navbarScrollTicking = false;

function updateNavbarOnScroll() {
    if (window.scrollY > 10) {
        navbar.classList.add("scrolled");
    } else {
        navbar.classList.remove("scrolled");
    }

    if (heroButtons) {
        const heroButtonsBottom = heroButtons.getBoundingClientRect().bottom;

        if (heroButtonsBottom <= navbar.offsetHeight + 10) {
            navbar.classList.add("show-buttons");
        } else {
            navbar.classList.remove("show-buttons");
        }
    }

    navbarScrollTicking = false;
}

window.addEventListener("scroll", function () {
    if (!navbarScrollTicking) {
        window.requestAnimationFrame(updateNavbarOnScroll);
        navbarScrollTicking = true;
    }
});
