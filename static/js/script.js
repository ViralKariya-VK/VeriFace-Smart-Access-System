document.addEventListener("DOMContentLoaded", () => {
    const indicator = document.querySelector(".indicator");
    const items = document.querySelectorAll(".nav-bar ul li");

    function moveIndicatorTo(element) {
        const aTag = element.querySelector("a");
        const aRect = aTag.getBoundingClientRect();
        const ulRect = element.parentElement.getBoundingClientRect();
        const center = aRect.left + aRect.width / 2 - ulRect.left;

        indicator.style.left = `calc(${center}px - 2rem)`; // 2.5rem = half of indicator width
    }

    items.forEach((item) => {
        item.addEventListener("click", () => {
            document.querySelector(".nav-bar ul li.active")?.classList.remove("active");
            item.classList.add("active");
            moveIndicatorTo(item);
        });
    });

    // Initialize on page load
    const activeItem = document.querySelector(".nav-bar ul li.active") || items[0];
    activeItem.classList.add("active");
    moveIndicatorTo(activeItem);
});
