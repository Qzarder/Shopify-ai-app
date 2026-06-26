import { useEffect } from "react";
import { Page, Layout, Card, BlockStack, Text, List, Banner, Button } from "@shopify/polaris";
import { TitleBar } from "@shopify/app-bridge-react";
import { useSubmit, useActionData } from "react-router";
import { authenticate, MONTHLY_PLAN } from "../shopify.server";

export const loader = async ({ request }) => {
  await authenticate.admin(request);
  return null;
};

// Own Billing API action so the upgrade flow runs on THIS page directly
// (no bounce through the Home route).
export const action = async ({ request }) => {
  const { billing, session } = await authenticate.admin(request);
  const { shop } = session;
  const url = new URL(request.url);
  const pathParts = url.pathname.split("/");
  const appHandle = pathParts[pathParts.indexOf("apps") + 1] || "csv-magic-cleaner";
  const returnUrl = `https://${shop}/admin/apps/${appHandle}/app`;

  try {
    await billing.require({
      plans: [MONTHLY_PLAN],
      onFailure: async () => {
        throw await billing.request({ plan: MONTHLY_PLAN, returnUrl });
      },
    });
    return { success: true };
  } catch (error) {
    if (error instanceof Response && error.status === 401) {
      const redirectUrl = error.headers.get("X-Shopify-API-Request-Failure-Reauthorize-Url");
      if (redirectUrl) {
        return { redirectUrl };
      }
    }
    throw error;
  }
};

export default function HowToUsePage() {
  const submit = useSubmit();
  const actionData = useActionData();

  useEffect(() => {
    if (actionData?.redirectUrl) {
      window.open(actionData.redirectUrl, "_top");
    }
  }, [actionData]);

  // Trigger the Billing API upgrade flow on this page directly.
  const goToPricing = () => submit({}, { method: "post" });

  return (
    <Page>
      <TitleBar title="How to Use" />
      <Layout>
        <Layout.Section>
          <Banner tone="info">
            <BlockStack gap="200">
              <Text as="p" variant="bodyMd" fontWeight="bold">Free plan: process up to 150 products per month — no payment required to get started.</Text>
              <Text as="p" variant="bodyMd">
                Once you reach the 150-product limit, upgrade to the Pro plan ($19.99/mo).
                All payments are handled securely through Shopify's checkout — no external accounts or credit cards entered outside of Shopify.
              </Text>
              <Text as="p" variant="bodyMd">
                Pro plan unlocks: <strong>unlimited products</strong>, AI-generated <strong>SEO titles</strong>, <strong>meta descriptions</strong>, and <strong>image alt text</strong>.
              </Text>
              <div>
                <Button onClick={goToPricing} variant="primary">
                  Upgrade to Pro — $19.99/mo
                </Button>
              </div>
            </BlockStack>
          </Banner>
        </Layout.Section>
        <Layout.Section>
          <Banner tone="warning">
            <BlockStack gap="100">
              <Text as="p" variant="bodyMd" fontWeight="bold">Authorized products only</Text>
              <Text as="p" variant="bodyMd">
                This app only processes product data from CSV files that you upload. You must own the products you import,
                or have the proper rights to import, list, and sell them (for example, your own catalog, officially licensed
                products, or products from a supplier you have a dropshipping agreement with). The app does not scrape or copy
                product data from other stores or websites.
              </Text>
            </BlockStack>
          </Banner>
        </Layout.Section>
        <Layout.Section>
          <Card>
            <BlockStack gap="400">
              <Text as="h2" variant="headingMd">Getting Started</Text>
              <List type="number">
                <List.Item>Export a product CSV file from your own supplier or product catalog</List.Item>
                <List.Item>Go to the <strong>Home</strong> page and upload your CSV file</List.Item>
                <List.Item>Choose a Tone of Voice for the AI copywriter</List.Item>
                <List.Item>Optionally enter a supplier name to save the column mapping for future uploads</List.Item>
                <List.Item>Click <strong>Start AI Magic</strong> and wait for processing to complete</List.Item>
                <List.Item>Preview the results, then click <strong>Import to Shopify Store</strong></List.Item>
              </List>
            </BlockStack>
          </Card>
        </Layout.Section>
        <Layout.Section>
          <Card>
            <BlockStack gap="400">
              <Text as="h2" variant="headingMd">Tone of Voice Options</Text>
              <List>
                <List.Item><strong>Neutral &amp; Professional</strong> — clear, balanced descriptions suitable for any product</List.Item>
                <List.Item><strong>Enthusiastic &amp; Sales-driven</strong> — high energy, persuasive copy that drives conversions</List.Item>
                <List.Item><strong>Luxury &amp; Elegant</strong> — rich, sensory language for premium products</List.Item>
                <List.Item><strong>Fun &amp; Playful</strong> — upbeat tone with personality, great for gifts and novelty items</List.Item>
                <List.Item><strong>Minimalist &amp; Direct</strong> — spec-focused, no-fluff descriptions for technical products</List.Item>
              </List>
            </BlockStack>
          </Card>
        </Layout.Section>
        <Layout.Section>
          <Card>
            <BlockStack gap="400">
              <Text as="h2" variant="headingMd">Pro Plan Features</Text>
              <List>
                <List.Item>Unlimited product processing (free plan: 150 products/month)</List.Item>
                <List.Item>AI-generated SEO Title &amp; Meta Description</List.Item>
                <List.Item>AI-generated Image Alt Text</List.Item>
              </List>
            </BlockStack>
          </Card>
        </Layout.Section>
      </Layout>
    </Page>
  );
}
