import { authenticate } from "../shopify.server";
import db from "../db.server";

export const action = async ({ request }) => {
  const { payload, session, topic, shop } = await authenticate.webhook(request);

  console.log(`Received ${topic} webhook for ${shop}`);
  const current = payload.current;

  new Response();

  if (session) {
    db.session.update({
      where: {
        id: session.id,
      },
      data: {
        scope: current.toString(),
      },
    }).catch(err => {
      console.error(`Failed to update session for ${shop}:`, err);
    });
  }

  return new Response(null, { status: 200 });
};
