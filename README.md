# 📖 FAQ

## 💬 How do I open the chat?
You can open the chat by right-clicking the system tray icon and selecting **“Open Chat.”**

<img  height="300" alt="image" src="https://github.com/user-attachments/assets/21ee5c18-4195-43c9-91cf-2fb76724ca00" />

## ❓ What questions can I ask?
You can ask anything about the following data tracked by PersonalQuery:

- **Window Activities** – Which applications were active and when.
- **Input Activities** – Total keystrokes and mouse movements.
- **Productivity** – Your self-reported productivity levels (if you have answered the hourly prompts).

If you’re unsure what to ask, you can:
- Type *“What can I ask?”* in the chat to get suggestions.
- Use the **suggested questions** shown above the chat input when you start a new conversation.

### ⚡ Quick Start – Suggested Questions

If you’re unsure what to ask, you can use the **Quick Start Suggested Questions** shown when you open a new chat.

<img width="1352" height="163" alt="image" src="https://github.com/user-attachments/assets/c9055111-6540-4ddd-ab49-4b30db3a83b4" />

When you click on one of these suggestions, a pop-up appears where you can pick a **time scope**.  
In this pop-up, you will also see **which days you have collected data**, so you can choose an appropriate timeframe.

<img height="350" alt="image" src="https://github.com/user-attachments/assets/38a2342f-3a0d-49b1-81ff-e4c1204b3e4c" />

## ⚙️ What are the Options?
<img width="1416" height="149" alt="image" src="https://github.com/user-attachments/assets/bcefad85-0a05-4ab3-aab8-29fef08e78ec" />


### Consent
- **Auto Approve**  
  - **Enabled**: All data queries are automatically approved and sent to OpenAI for processing.
  - **Disabled**: You can review, edit, approve, or reject each query before it is sent.

### SQL
- **Limit Results Slider**
  - Limits the number of records returned in a query.
  - A higher limit may make answer generation take longer.

- **Auto SQL**
  - **Enabled**: Queries are executed immediately without manual review.
  - **Disabled**: You can review and edit the generated SQL query before it runs.

### Response Style
- **Granularity**
  - **Low**: Concise, high-level answers with key insights only.
  - **High**: Detailed, in-depth answers.
  - **Auto**: The system decides the appropriate level of detail.

- **Visualization**
  - **Always**: Always include a visualization (e.g., charts).
  - **Never**: Never include a visualization.
  - **Auto**: The system decides whether to include a visualization.

## 🛑 Known Issues

### Windows-specific
- **Backend Process Window**
  - You might see a terminal window appear when starting PersonalQuery.
  - For now, simply minimize this window.

### macOS-specific
- **Backend Process Persistence**
  - When quitting the app, the backend process may keep running.
  - To terminate it manually, open **Activity Monitor**, search for `pq-backend`, and force quit it.
