import { useEffect, useState } from "react";
import { Page, Layout, Card, BlockStack, Text, List, Banner, Button, Badge } from "@shopify/polaris";
import { TitleBar } from "@shopify/app-bridge-react";
import { useSubmit, useActionData, useLoaderData } from "react-router";
import { authenticate, MONTHLY_PLAN } from "../shopify.server";

export const loader = async ({ request }) => {
  const { billing } = await authenticate.admin(request);
  const checkResult = await billing.check({ plans: [MONTHLY_PLAN] });
  const isPro = checkResult === true || checkResult?.hasActivePayment === true;
  return { isPro };
};

// Own Billing API action so upgrade/downgrade run on THIS page directly
// (no bounce through the Home route).
export const action = async ({ request }) => {
  const { billing, session } = await authenticate.admin(request);
  const { shop } = session;
  const formData = await request.formData();
  const downgrade = formData.get("downgrade") === "true";

  if (downgrade) {
    // 1.2.3: merchants must be able to move from Pro back to Free without
    // contacting support or reinstalling the app, and the cancellation must be
    // confirmed in the merchant's app charge history (Settings > Billing).
    const { appSubscriptions } = await billing.check({ plans: [MONTHLY_PLAN] });
    const activeSub = appSubscriptions?.[0];

    if (!activeSub) {
      return { downgraded: true };
    }

    try {
      const cancelled = await billing.cancel({ subscriptionId: activeSub.id, prorate: true });
      if (cancelled?.status !== "CANCELLED") {
        return { downgradeError: `Subscription status after cancel: ${cancelled?.status || "unknown"}` };
      }
      return { downgraded: true };
    } catch (err) {
      return { downgradeError: err instanceof Error ? err.message : "Failed to cancel subscription" };
    }
  }

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
  const { isPro } = useLoaderData();
  const submit = useSubmit();
  const actionData = useActionData();
  const [isDowngrading, setIsDowngrading] = useState(false);

  useEffect(() => {
    if (actionData?.redirectUrl) {
      window.open(actionData.redirectUrl, "_top");
    }
    if (actionData?.downgraded || actionData?.downgradeError) {
      setIsDowngrading(false);
    }
  }, [actionData]);

  // Trigger the Billing API upgrade flow on this page directly.
  const goToPricing = () => submit({}, { method: "post" });

  const goToDowngrade = () => {
    setIsDowngrading(true);
    const fd = new FormData();
    fd.append("downgrade", "true");
    submit(fd, { method: "post" });
  };

  return (
    <Page>
      <TitleBar title="How to Use" />
      <Layout>
        <Layout.Section>
          <Banner tone="info">
            <BlockStack gap="200">
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <Text as="p" variant="bodyMd" fontWeight="bold">
                  {isPro ? "You're on the Pro plan" : "Free plan: process up to 150 products per month"}
                </Text>
                {isPro && <Badge tone="success">Pro Plan Active</Badge>}
              </div>
              {isPro ? (
                <Text as="p" variant="bodyMd">
                  $19.99/mo, unlimited products. You can cancel anytime — your plan moves back to Free
                  immediately and the cancellation is reflected in your store's billing history.
                </Text>
              ) : (
                <>
                  <Text as="p" variant="bodyMd">
                    Once you reach the 150-product limit, upgrade to the Pro plan ($19.99/mo).
                    All payments are handled securely through Shopify's checkout — no external accounts or credit cards entered outside of Shopify.
                  </Text>
                  <Text as="p" variant="bodyMd">
                    Pro plan unlocks: <strong>unlimited products</strong>, AI-generated <strong>SEO titles</strong>, <strong>meta descriptions</strong>, and <strong>image alt text</strong>.
                  </Text>
                </>
              )}
              <div>
                {isPro ? (
                  <Button onClick={goToDowngrade} variant="primary" tone="critical" loading={isDowngrading} disabled={isDowngrading}>
                    Downgrade to Free
                  </Button>
                ) : (
                  <Button onClick={goToPricing} variant="primary">
                    Upgrade to Pro — $19.99/mo
                  </Button>
                )}
              </div>
              {actionData?.downgraded && (
                <Banner tone="success">You're now on the Free plan (up to 150 products/month).</Banner>
              )}
              {actionData?.downgradeError && (
                <Banner tone="critical">Could not cancel your subscription: {actionData.downgradeError}. Please try again.</Banner>
              )}
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
