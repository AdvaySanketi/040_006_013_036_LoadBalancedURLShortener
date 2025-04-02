import 'dotenv/config';
import express from 'express';
import { createClient } from 'redis';
import { nanoid } from 'nanoid';
import fetch from 'node-fetch';

const app = express();
app.use(express.json());

app.use((req, res, next) => {
    console.log(req.path, req.method);
    next();
});

const REDIS_HOST = process.env.REDIS_HOST || "localhost";
const REDIS_PORT = process.env.REDIS_PORT || "6379";
const REDIS_PASSWORD = process.env.REDIS_PASSWORD || "";

const client = createClient({
    url: `redis://default:${REDIS_PASSWORD}@${REDIS_HOST}:${REDIS_PORT}`
});

await client.connect().catch(err => console.error("Redis Connection Error:", err));

const BASE_URL = process.env.BASE_URL || "http://localhost:5000";

const checkUrlExists = async (url) => {
    try {
        const response = await fetch(url, { method: 'HEAD' });
        return response.ok;
    } catch (error) {
        return false;
    }
};

app.post("/shorten", async (req, res) => {
    const { url } = req.body;
    if (!url) return res.status(400).json({ "error": "`url` is required" });

    const isValid = await checkUrlExists(url);
    if (!isValid) {
        return res.status(400).json({ "error": "Invalid or non-existing URL" });
    }

    const existingShortId = await client.get(`long:${url}`);
    if (existingShortId) {
        return res.status(200).json({ "shortened_url": `${BASE_URL}/${existingShortId}` });
    }

    const shortId = nanoid(12);
    await client.set(`short:${shortId}`, url);
    await client.set(`long:${url}`, shortId);

    res.status(201).json({ "shortened_url": `${BASE_URL}/${shortId}` });
});

app.get("/getAll", async (req, res) => {
    try {
        let cursor = "0";
        let allRecords = {};

        do {
            const reply = await client.scan(cursor, { MATCH: "short:*", COUNT: 100 });
            cursor = reply.cursor;
            const keys = reply.keys;

            if (keys.length > 0) {
                const values = await client.mGet(keys);
                keys.forEach((key, index) => {
                    allRecords[key.replace("short:", "")] = values[index];
                });
            }
        } while (cursor !== "0");

        res.json(allRecords);
    } catch (error) {
        console.error("Error fetching all records:", error);
        res.status(500).json({ error: "Internal Server Error" });
    }
});

app.get("/:shortenedId", async (req, res) => {
    const { shortenedId } = req.params;
    const longUrl = await client.get(`short:${shortenedId}`);

    if (!longUrl) return res.status(404).json({ "error": "URL not found" });
    res.redirect(longUrl);
});

const PORT = process.env.PORT || 5000;
app.listen(PORT, '0.0.0.0', () => {
    console.log(`Server running at ${BASE_URL}`);
});
