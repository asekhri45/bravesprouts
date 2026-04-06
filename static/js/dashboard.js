document.addEventListener("DOMContentLoaded", function () {
    const currentProfileIcon = document.getElementById("currentProfileIcon");
    const iconOptions = document.querySelectorAll(".icon-option");

    iconOptions.forEach((button) => {
        button.addEventListener("click", async function () {
            const selectedIcon = this.dataset.icon;
            if (!selectedIcon || !currentProfileIcon) return;

            currentProfileIcon.src = `/static/images/${selectedIcon}`;

            try {
                const response = await fetch("/update-profile-icon", {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/x-www-form-urlencoded",
                    },
                    body: new URLSearchParams({
                        icon: selectedIcon
                    })
                });

                const data = await response.json();

                if (!data.success) {
                    console.error(data.error || "Failed to save icon");
                }
            } catch (error) {
                console.error("Error saving profile icon:", error);
            }
        });
    });
});