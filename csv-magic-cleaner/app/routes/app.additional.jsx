import { Page, Layout, Card, BlockStack, Text, List } from "@shopify/polaris";
import { TitleBar } from "@shopify/app-bridge-react";

export default function HowToUsePage() {
  return (
    <Page>
      <TitleBar title="How to Use" />
      <Layout>
        <Layout.Section>
          <Card>
            <BlockStack gap="400">
              <Text as="h2" variant="headingMd">Getting Started</Text>
              <List type="number">
                <List.Item>Export a product CSV file from your own supplier or product catalog</List.Item>
                <List.Item>Go to the Home page and upload your CSV file</List.Item>
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
