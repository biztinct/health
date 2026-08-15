/** @odoo-module **/

const initializeEditorialHomepage = () => {
    const root = document.querySelector(".thhs-editorial-intro");
    if (!root || root.dataset.editorialReady) {
        return;
    }
    root.dataset.editorialReady = "1";

    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const reveals = document.querySelectorAll(".thhs-editorial-reveal");
    if (reducedMotion || !("IntersectionObserver" in window)) {
        reveals.forEach((element) => element.classList.add("is-visible"));
        return;
    }

    const observer = new IntersectionObserver(
        (entries) => {
            for (const entry of entries) {
                if (entry.isIntersecting) {
                    entry.target.classList.add("is-visible");
                    observer.unobserve(entry.target);
                }
            }
        },
        { threshold: 0.12 }
    );
    reveals.forEach((element) => observer.observe(element));
};

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initializeEditorialHomepage, { once: true });
} else {
    initializeEditorialHomepage();
}
