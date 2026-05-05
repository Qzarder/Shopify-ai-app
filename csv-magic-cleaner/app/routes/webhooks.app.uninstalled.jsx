import { authenticate } from "../shopify.server";
import db from "../db.server";

export const action = async ({ request }) => {
  const { shop, session, topic } = await authenticate.webhook(request);

  console.log(`Received ${topic} webhook for ${shop}`);

  new Response();

  if (session) {
    db.session.deleteMany({ where: { shop } }).catch(err => {
      console.error(`Failed to delete sessions for ${shop}:`, err);
    });
  }

  return new Response(null, { status: 200 });
};
