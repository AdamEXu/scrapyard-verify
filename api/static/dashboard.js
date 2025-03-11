let userData = null;

// Fetch and store user data
fetch("/api/user_info", {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
  },
  credentials: "include",
})
  .then((response) => response.json())
  .then((data) => {
    userData = data;
    console.log("User data loaded:", userData);
    onUserDataLoaded();
    // cache user data in local storage
    localStorage.setItem("userData", JSON.stringify(userData));
  })
  .catch((error) => console.error("Error:", error));

var currentPanel = "dashboard";

// Make switchPanel available globally
window.switchPanel = function (panelId, smooth = true) {
  currentPanel = panelId;
  // scroll horizontally to the panel
  const panel = document.getElementById(panelId);
  panel.scrollIntoView({
    behavior: smooth ? "smooth" : "auto",
    inline: "center",
    duration: 500,
  });
  // change url
  if (panelId === "dashboard") {
    window.history.pushState({}, "", "/dashboard");
    return;
  }
  window.history.pushState({}, "", `/dashboard/${panelId}`);
};

// Handle window resize
let resizeTimeout;
window.addEventListener("resize", () => {
  clearTimeout(resizeTimeout);
  resizeTimeout = setTimeout(() => {
    switchPanel(currentPanel, false);
  }, 0);
});

document.addEventListener("DOMContentLoaded", function () {
  const navItems = document.querySelectorAll(".nav-item");
  navItems.forEach((item) => {
    item.addEventListener("click", function (event) {
      event.preventDefault();
      const panelId = this.getAttribute("to");
      switchPanel(panelId);
    });
  });

  const linksToDashboard = document.querySelectorAll("a");
  linksToDashboard.forEach((link) => {
    const href = link.getAttribute("href");
    if (href && href.startsWith("/dashboard")) {
      link.addEventListener("click", function (event) {
        event.preventDefault();
        const panelId = link.getAttribute("href").split("/").pop();
        switchPanel(panelId);
      });
    }
  });
});

function onUserDataLoaded() {
  const nameElements = document.getElementsByClassName("name");
  for (let i = 0; i < nameElements.length; i++) {
    nameElements[i].textContent = userData.preferredName;
  }
  document.querySelector(".status").textContent = userData.waitlist;
  if (userData.waitlist === "approved") {
    document.querySelector("#message").textContent =
      "We're looking forward to seeing you at the event. Keep an eye on your email for more details! Don't forget to join our Discord server for updates and announcements as well.";
  } else {
    document.querySelector("#message").textContent =
      "You're on the waitlist. We'll send you an email when you're approved. Want to get off the waitlist faster? Get your parents to chaperone! More details on our Discord server.";
  }
  if (userData.organizerNotes.mealForm) {
    document.querySelector("#meal-msg").innerHTML =
      "Yay you, you already filled out the meal form! You're good to go for now, but you can change it <a href='/dashboard/meal-form' class='link'><span></span><span>here</span></a>.";
  } else {
    document.querySelector("#meal-msg").innerHTML =
      "You haven't filled out the meal form yet. Please do so <a href='/dashboard/meal-form' class='link'><span></span><span>here</span></a> or you won't get any food.";
  }
}

function useCachedUserData() {
  const cachedData = localStorage.getItem("userData");
  if (cachedData) {
    userData = JSON.parse(cachedData);
    onUserDataLoaded();
  }
}

useCachedUserData();
