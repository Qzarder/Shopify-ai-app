import { redirect } from "react-router";
import { login } from "../../shopify.server";

export const loader = async ({ request }) => {
  const url = new URL(request.url);
  
  if (url.searchParams.get("shop")) {
    // Правильный редирект для новых версий шаблона
    throw redirect(`/app?${url.searchParams.toString()}`);
  }
  
  return await login(request);
};

// Здесь НЕ ДОЛЖНО быть никакого интерфейса, DropZone, Page или Card. Только null.
export default function App() {
  return null;
}