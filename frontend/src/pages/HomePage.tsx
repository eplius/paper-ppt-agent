import { Link } from "react-router-dom";
import { useLocale } from "../i18n";
import { Layout } from "../components/layout/Layout";

export function HomePage() {
  const { t } = useLocale();

  return (
    <Layout showSidebar={false} contentClassName="home-layout">
      <section className="home-minimal reveal-up">
        <h1 className="home-minimal-title">Paper PPT Agent</h1>
        <div className="home-minimal-actions">
          <Link to="/generate?fresh=1" className="primary-button">
            {t("home.start")}
          </Link>
        </div>
      </section>
    </Layout>
  );
}
