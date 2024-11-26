const express = require("express");
const { Pool } = require("pg");
const cors = require("cors");

const app = express();
app.use(cors());

// PostgreSQL connection pool
const pool = new Pool({
  user: "postgres",
  host: "192.168.42.185",
  database: "Train_Databse",
  password: "root",
  port: 5432, 
});

// API endpoint to fetch data
app.get("/data", async (req, res) => {
  try {
    const result = await pool.query("SELECT * FROM train_data");
    res.json(result.rows);
  } catch (err) {
    console.error(err);
    res.status(500).send("Error fetching data");
  }
});

// Start the server
const PORT = 3000;
app.listen(PORT, () => {
  console.log(`Server running on http://localhost:${PORT}`);
});


async function fetchDataAndDisplay() {
    try {
      const response = await fetch("http://localhost:3000/data");
      const data = await response.json();
  
      // Select the container where cards will be displayed
      const container = document.getElementById("train-list");
  
      // Clear existing content
      container.innerHTML = "";
  
      // Create cards for each item
      data.forEach((item) => {
        const card = document.createElement("div");
        card.className = "card";
        card.style = "border: 1px solid #ccc; border-radius: 5px; padding: 10px; margin-bottom: 10px;";
  
        // Customize card content
        card.innerHTML = `
          <h3>${item.title}</h3>
          <p>${item.description}</p>
          <p><strong>Price:</strong> ${item.price}</p>
        `;
  
        container.appendChild(card);
      });
    } catch (err) {
      console.error("Error fetching data:", err);
    }
  }
  
  // Call the function on page load
  fetchDataAndDisplay();