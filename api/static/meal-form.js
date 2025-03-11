// Remove duplicate declaration since it's already declared
// let config = null;

// Use the existing userData from dashboard.js
function initializeMealForm() {
  // Fetch meal form configuration
  fetch("/static/meal-form.json")
    .then((response) => {
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      return response.json();
    })
    .then((configData) => {
      console.log("Received config data:", configData); // Debug log

      if (!configData) {
        throw new Error("No configuration data received");
      }

      if (!Array.isArray(configData.sections)) {
        throw new Error("Configuration must have a 'sections' array");
      }

      config = configData; // Store the config globally
      const container = document.getElementById("mealFormContainer");
      container.innerHTML = "";

      config.sections.forEach((section) => {
        const sectionDiv = document.createElement("div");
        sectionDiv.className = "form-section";

        const title = document.createElement("h2");
        title.textContent = section.name;
        sectionDiv.appendChild(title);

        section.fields.forEach((field) => {
          const fieldDiv = document.createElement("div");
          fieldDiv.className = "form-field";

          const label = document.createElement("label");
          label.textContent = field.name;
          fieldDiv.appendChild(label);

          // Add description if it exists
          if (field.description) {
            const description = document.createElement("p");
            description.className = "field-description";
            description.textContent = field.description;
            fieldDiv.appendChild(description);
          }

          if (field.type === "select-multiple") {
            // Create a container for checkboxes
            const optionsContainer = document.createElement("div");
            optionsContainer.className = "meal-options-grid";

            field.options.forEach((option) => {
              const card = document.createElement("div");
              card.className = "meal-option-card";

              // Create checkbox input
              const checkbox = document.createElement("input");
              checkbox.type = "checkbox";
              checkbox.className = "hidden-radio"; // Using the same class as radio buttons
              checkbox.name = `${section.id}-${field.id}`;
              checkbox.value = option.value;
              checkbox.id = `${section.id}-${field.id}-${option.value}`;

              // Create card content
              const info = document.createElement("div");
              info.className = "meal-option-info";

              const name = document.createElement("h3");
              name.textContent = option.name;

              const description = document.createElement("p");
              description.textContent = option.description;

              info.appendChild(name);
              info.appendChild(description);

              card.appendChild(checkbox);
              card.appendChild(info);

              // Add click handler
              card.addEventListener("click", () => {
                checkbox.checked = !checkbox.checked;
                card.classList.toggle("selected", checkbox.checked);
              });

              optionsContainer.appendChild(card);
            });

            fieldDiv.appendChild(optionsContainer);
          } else {
            // Existing code for regular select type
            const optionsGrid = document.createElement("div");
            optionsGrid.className = "meal-options-grid";

            field.options.forEach((option) => {
              const card = document.createElement("div");
              card.className = "meal-option-card";

              // Create hidden radio input
              const radio = document.createElement("input");
              radio.type = "radio";
              radio.className = "hidden-radio";
              radio.name = `${section.id}-${field.id}`;
              radio.value = option.value;
              radio.id = `${section.id}-${field.id}-${option.value}`;

              // Create card content
              if (option.image) {
                const img = document.createElement("img");
                img.src = option.image;
                img.alt = option.name;
                card.appendChild(img);
              }

              const info = document.createElement("div");
              info.className = "meal-option-info";

              const name = document.createElement("h3");
              name.textContent = option.name;

              const description = document.createElement("p");
              description.textContent = option.description;

              info.appendChild(name);
              info.appendChild(description);

              card.appendChild(radio);
              card.appendChild(info);

              // Add click handler
              card.addEventListener("click", () => {
                optionsGrid
                  .querySelectorAll(".meal-option-card")
                  .forEach((c) => {
                    c.classList.remove("selected");
                  });
                card.classList.add("selected");
                radio.checked = true;
              });

              optionsGrid.appendChild(card);
            });

            fieldDiv.appendChild(optionsGrid);
          }

          sectionDiv.appendChild(fieldDiv);
        });

        container.appendChild(sectionDiv);
      });

      // Load existing preferences if available
      if (
        userData &&
        userData.organizerNotes &&
        userData.organizerNotes.mealForm
      ) {
        const mealPrefs = userData.organizerNotes.mealForm;
        for (const sectionId in mealPrefs) {
          const section = mealPrefs[sectionId];
          for (const fieldId in section) {
            const value = section[fieldId];
            const radio = document.querySelector(
              `input[name="${sectionId}-${fieldId}"][value="${value}"]`
            );
            if (radio) {
              radio.checked = true;
              // Add selected class to parent card
              const card = radio.closest(".meal-option-card");
              if (card) {
                card.classList.add("selected");
              }
            }
          }
        }
      }
    })
    .catch((error) => {
      console.error("Error loading meal form:", error);
      const container = document.getElementById("mealFormContainer");
      container.innerHTML = `
        <div style="color: red; padding: 20px;">
          <p>Error loading meal form: ${error.message}</p>
          <p>Please try refreshing the page. If the problem persists, contact support.</p>
        </div>
      `;
    });
}

// Wait for userData to be loaded from the server (not cached)
document.addEventListener("DOMContentLoaded", () => {
  // Show loading state
  const container = document.getElementById("mealFormContainer");
  container.innerHTML = "<p>Loading meal form...</p>";

  // Wait for fresh user data
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
      initializeMealForm(); // This will now handle both form creation and preference loading
    })
    .catch((error) => {
      console.error("Error loading user data:", error);
      container.innerHTML = `
        <div style="color: red; padding: 20px;">
          <p>Error loading user data. Please try refreshing the page.</p>
        </div>
      `;
    });
});

function saveMealForm() {
  const formData = {
    "saturday-lunch": {},
    "saturday-dinner": {},
    "sunday-breakfast": {},
  };

  let missingFields = [];

  // Saturday Lunch - Pizza
  const saturdayLunch = document.querySelector(
    'input[name="saturday-lunch-pizza"]:checked'
  );
  if (
    !saturdayLunch &&
    !document.querySelector(
      'input[name="saturday-lunch-pizza"][value="skip"]:checked'
    )
  ) {
    missingFields.push("Saturday Lunch - Pizza Selection");
  } else if (saturdayLunch) {
    formData["saturday-lunch"].pizza = saturdayLunch.value;
  }

  // Saturday Dinner - iniBurger
  const saturdayDinnerBurger = document.querySelector(
    'input[name="saturday-dinner-iniburger"]:checked'
  );
  if (
    !saturdayDinnerBurger &&
    !document.querySelector(
      'input[name="saturday-dinner-iniburger"][value="skip"]:checked'
    )
  ) {
    missingFields.push("Saturday Dinner - Burger Selection");
  } else if (saturdayDinnerBurger) {
    formData["saturday-dinner"].iniburger = saturdayDinnerBurger.value;
  }

  // Saturday Dinner - Side
  const side = document.querySelector(
    'input[name="saturday-dinner-side"]:checked'
  );
  if (!side && saturdayDinnerBurger && saturdayDinnerBurger.value !== "skip") {
    missingFields.push("Saturday Dinner - Side Selection");
  } else if (side) {
    formData["saturday-dinner"].side = side.value;
  }

  // Sunday Breakfast - Donuts
  const sundayBreakfast = document.querySelector(
    'input[name="sunday-breakfast-donuts"]:checked'
  );
  if (
    !sundayBreakfast &&
    !document.querySelector(
      'input[name="sunday-breakfast-donuts"][value="no"]:checked'
    )
  ) {
    missingFields.push("Sunday Breakfast Selection");
  } else if (sundayBreakfast) {
    formData["sunday-breakfast"].donuts = sundayBreakfast.value;
  }

  // Dietary Restrictions for each section
  const allSections = ["saturday-lunch", "saturday-dinner", "sunday-breakfast"];
  allSections.forEach((section) => {
    const dietaryChecks = document.querySelectorAll(
      `input[name="${section}-dietary-restrictions"]:checked`
    );
    if (dietaryChecks.length > 0) {
      formData[section]["dietary-restrictions"] = Array.from(dietaryChecks).map(
        (check) => check.value
      );
    }
  });

  if (missingFields.length > 0) {
    Toastify({
      text: "Please select: " + missingFields.join(", "),
      duration: 5000,
      gravity: "bottom",
      position: "right",
      style: {
        background: "#ff4444",
      },
    }).showToast();
    return;
  }

  console.log("Sending form data:", formData);

  fetch("/api/set-meal-form", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    credentials: "include",
    body: JSON.stringify(formData),
  })
    .then(async (response) => {
      const text = await response.text();
      console.log("Raw server response:", text);

      if (!response.ok) {
        try {
          const json = JSON.parse(text);
          throw new Error(json.error || "Failed to save preferences");
        } catch (e) {
          if (response.status === 401) {
            throw new Error(
              "Session expired. Please refresh the page and try again."
            );
          }
          throw new Error(
            `Server error (${response.status}). Please try again.`
          );
        }
      }

      try {
        return JSON.parse(text);
      } catch (e) {
        throw new Error("Invalid JSON response from server");
      }
    })
    .then((data) => {
      if (data.success) {
        Toastify({
          text: "Meal preferences saved successfully!",
          duration: 3000,
          gravity: "bottom",
          position: "right",
          style: {
            background: "#4CAF50",
          },
        }).showToast();
      } else {
        throw new Error(data.error || "Failed to save preferences");
      }
    })
    .catch((error) => {
      console.error("Error saving preferences:", error);
      Toastify({
        text: error.message || "Error saving preferences. Please try again.",
        duration: 5000,
        gravity: "bottom",
        position: "right",
        style: {
          background: "#ff4444",
        },
      }).showToast();
    });
}
