export const agenticPageTalkTrack = [
    {
        heading: "Instructions and Talk Track",
        content: [
            {
                heading: "Solution Overview",
                body: "The Agentic Framework serves as a versatile AI-driven recommendation assistant capable of comprehending your data, performing a multi-step diagnostic workflow using LangGraph, and generating actionable recommendations. The framework integrates several key technologies. It reads timeseries data from a CSV file or MongoDB (simulating various data inputs), generates text embeddings using the Cohere English V3 model, performs vector searches to identify similar past queries from MongoDB, persists session and run data, and finally generates a diagnostic recommendation. MongoDB stores agent profiles, historical recommendations, timeseries data, session logs, and more. This persistent storage not only logs every step of the diagnostic process for traceability but also enables efficient querying and reusability of past data.",
            },
            {
                heading: "How to Demo",
                body: [
                    "Choose “New Diagnosis.",
                    "Enter a query in the text box (e.g., the sample complaint about a knocking sound).",
                    "Click the “Run Agent” button and wait for a few minutes as the agent finishes its run.",
                    "The workflow, chain-of-thought output, and the final recommendation are shown in the left column.",
                    "In the right column, the documents shown are the records inserted during the current agent run.",
                ],
            },
        ],
    },
    {
        heading: "Behind the Scenes",
        content: [
            {
                heading: "Logical Architecture",
                body: "",
            },
            {
                image: {
                    src: "./info.png",
                    alt: "Logical Architecture",
                },
            },
        ],
    },
    {
        heading: "Why MongoDB?",
        content: [
            {
                heading: "Flexible Data Model",
                body: `<div>MongoDB's <a href="https://www.mongodb.com/resources/basics/databases/document-databases" target="_blank">document-oriented architecture</a> allows you to store varied data 
                (such as <i>timeseries logs, agent profiles, and recommendation outputs</i>) 
                in a <strong>single unified format</strong>. This flexibility means you don’t have to redesign your database <mark>schema</mark> every time your data requirements evolve.</div>`,
                isHTML:true
            },
            {
                heading: "Scalability and Performance",
                body: "MongoDB is designed to scale horizontally, making it capable of handling large volumes of real-time data. This is essential when multiple data sources send timeseries data simultaneously, ensuring high performance under heavy load.",
            },
            {
                heading: "Real-Time Analytics",
                body: "With powerful aggregation frameworks and change streams, MongoDB supports real-time data analysis and anomaly detection. This enables the system to process incoming timeseries data on the fly and quickly surface critical insights.",
            },
            {
                heading: "Seamless Integration",
                body: "MongoDB is seamlessly integrated with LangGraph, making it a powerful memory provider.",
            },
            {
                heading: "Vector Search",
                body: "MongoDB Atlas supports native vector search, enabling fast and efficient similarity searches on embedding vectors. This is critical for matching current queries with historical data, thereby enhancing diagnostic accuracy and providing more relevant recommendations.",
            },
        ],
    },
]

// Add bellow the talk tracks for other sections/pages