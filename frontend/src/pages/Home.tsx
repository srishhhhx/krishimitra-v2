import { Button } from "@/components/ui/button";
import { useNavigate } from "react-router-dom";
import { Sprout, Shield, TrendingUp, Users } from "lucide-react";

const Home = () => {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-gradient-to-b from-green-50 to-white">
      {/* Navbar */}
      <nav className="border-b bg-white/80 backdrop-blur-sm sticky top-0 z-50">
        <div className="container mx-auto px-4 py-4 flex justify-between items-center">
          <div className="flex items-center gap-2">
            <Sprout className="h-8 w-8 text-green-600" />
            <span className="text-2xl font-bold text-green-800">Krishimitra</span>
          </div>
          <div className="flex gap-4">
            <Button variant="ghost" onClick={() => navigate("/about")}>
              About Us
            </Button>
            <Button onClick={() => navigate("/auth")}>
              Get Started
            </Button>
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="container mx-auto px-4 py-20 text-center">
        <h1 className="text-5xl md:text-6xl font-bold text-green-900 mb-6">
          Smart Agriculture Risk Assessment
        </h1>
        <p className="text-xl text-gray-600 mb-8 max-w-2xl mx-auto">
          Empower your farming decisions with AI-powered disease detection, 
          fertilizer recommendations, and real-time risk analysis
        </p>
        <div className="flex gap-4 justify-center">
          <Button size="lg" onClick={() => navigate("/auth")}>
            Start Free Trial
          </Button>
          <Button size="lg" variant="outline" onClick={() => navigate("/about")}>
            Learn More
          </Button>
        </div>
      </section>

      {/* Features Section */}
      <section className="container mx-auto px-4 py-16">
        <h2 className="text-3xl font-bold text-center mb-12">Why Choose Krishimitra?</h2>
        <div className="grid md:grid-cols-3 gap-8">
          <div className="bg-white p-6 rounded-lg shadow-lg text-center">
            <Shield className="h-12 w-12 text-green-600 mx-auto mb-4" />
            <h3 className="text-xl font-semibold mb-2">Risk Assessment</h3>
            <p className="text-gray-600">
              Real-time monitoring of weather patterns and crop risks to prevent losses
            </p>
          </div>
          <div className="bg-white p-6 rounded-lg shadow-lg text-center">
            <Sprout className="h-12 w-12 text-green-600 mx-auto mb-4" />
            <h3 className="text-xl font-semibold mb-2">Disease Detection</h3>
            <p className="text-gray-600">
              AI-powered image analysis to identify plant diseases early
            </p>
          </div>
          <div className="bg-white p-6 rounded-lg shadow-lg text-center">
            <TrendingUp className="h-12 w-12 text-green-600 mx-auto mb-4" />
            <h3 className="text-xl font-semibold mb-2">Smart Recommendations</h3>
            <p className="text-gray-600">
              Data-driven fertilizer and treatment suggestions for optimal yields
            </p>
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="bg-green-600 text-white py-16">
        <div className="container mx-auto px-4 text-center">
          <h2 className="text-3xl font-bold mb-4">Ready to Transform Your Farming?</h2>
          <p className="text-xl mb-8">Join thousands of farmers using Krishimitra</p>
          <Button size="lg" variant="secondary" onClick={() => navigate("/auth")}>
            Get Started Now
          </Button>
        </div>
      </section>

      {/* Footer */}
      <footer className="bg-gray-900 text-white py-8">
        <div className="container mx-auto px-4 text-center">
          <p>&copy; 2024 Krishimitra. All rights reserved.</p>
        </div>
      </footer>
    </div>
  );
};

export default Home;
