import { authenticate } from "../shopify.server";

export const action = async ({ request }) => {
  try {
    const { topic, shop, payload } = await authenticate.webhook(request);

    console.log(`Webhook received`);
    console.log(`Topic: ${topic}`);
    console.log(`Shop: ${shop}`);

    return new Response("OK", { status: 200 });

  } catch (error) {
    console.error("Webhook verification failed", error);

    return new Response("Unauthorized", { status: 401 });
  }
};