import { Button } from "@/components/ui/button";
import { useNavigate } from "react-router-dom";
import { Sprout, Target, Users, Award } from "lucide-react";

const About = () => {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Navbar */}
      <nav className="border-b bg-white sticky top-0 z-50">
        <div className="container mx-auto px-4 py-4 flex justify-between items-center">
          <div className="flex items-center gap-2 cursor-pointer" onClick={() => navigate("/")}>
            <Sprout className="h-8 w-8 text-green-600" />
            <span className="text-2xl font-bold text-green-800">Krishimitra</span>
          </div>
          <div className="flex gap-4">
            <Button variant="ghost" onClick={() => navigate("/")}>
              Home
            </Button>
            <Button onClick={() => navigate("/auth")}>
              Get Started
            </Button>
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="bg-gradient-to-r from-green-600 to-green-700 text-white py-20">
        <div className="container mx-auto px-4 text-center">
          <h1 className="text-5xl font-bold mb-6">About Krishimitra</h1>
          <p className="text-xl max-w-3xl mx-auto">
            Empowering farmers with cutting-edge technology to make informed decisions 
            and achieve sustainable agricultural success
          </p>
        </div>
      </section>

      {/* Mission Section */}
      <section className="container mx-auto px-4 py-16">
        <div className="grid md:grid-cols-2 gap-12 items-center">
          <div>
            <div className="flex items-center gap-2 mb-4">
              <Target className="h-8 w-8 text-green-600" />
              <h2 className="text-3xl font-bold">Our Mission</h2>
            </div>
            <p className="text-lg text-gray-700 mb-4">
              Krishimitra is dedicated to transforming agriculture through innovative technology. 
              We provide farmers with real-time insights, predictive analytics, and actionable 
              recommendations to optimize crop health and maximize yields.
            </p>
            <p className="text-lg text-gray-700">
              Our platform combines AI, machine learning, and agricultural expertise to deliver 
              a comprehensive solution for modern farming challenges.
            </p>
          </div>
          <div className="bg-white p-8 rounded-lg shadow-lg">
            <h3 className="text-2xl font-semibold mb-6">What We Offer</h3>
            <ul className="space-y-4">
              <li className="flex items-start gap-3">
                <div className="bg-green-100 p-2 rounded">
                  <Sprout className="h-5 w-5 text-green-600" />
                </div>
                <div>
                  <h4 className="font-semibold">Disease Detection</h4>
                  <p className="text-gray-600">AI-powered plant disease identification</p>
                </div>
              </li>
              <li className="flex items-start gap-3">
                <div className="bg-green-100 p-2 rounded">
                  <Target className="h-5 w-5 text-green-600" />
                </div>
                <div>
                  <h4 className="font-semibold">Risk Assessment</h4>
                  <p className="text-gray-600">Real-time weather and crop risk analysis</p>
                </div>
              </li>
              <li className="flex items-start gap-3">
                <div className="bg-green-100 p-2 rounded">
                  <Award className="h-5 w-5 text-green-600" />
                </div>
                <div>
                  <h4 className="font-semibold">Expert Recommendations</h4>
                  <p className="text-gray-600">Data-driven fertilizer and treatment advice</p>
                </div>
              </li>
            </ul>
          </div>
        </div>
      </section>

      {/* Values Section */}
      <section className="bg-white py-16">
        <div className="container mx-auto px-4">
          <h2 className="text-3xl font-bold text-center mb-12">Our Values</h2>
          <div className="grid md:grid-cols-3 gap-8">
            <div className="text-center">
              <div className="bg-green-100 w-16 h-16 rounded-full flex items-center justify-center mx-auto mb-4">
                <Users className="h-8 w-8 text-green-600" />
              </div>
              <h3 className="text-xl font-semibold mb-2">Farmer-Centric</h3>
              <p className="text-gray-600">
                Every feature is designed with the farmer's needs in mind
              </p>
            </div>
            <div className="text-center">
              <div className="bg-green-100 w-16 h-16 rounded-full flex items-center justify-center mx-auto mb-4">
                <Target className="h-8 w-8 text-green-600" />
              </div>
              <h3 className="text-xl font-semibold mb-2">Innovation</h3>
              <p className="text-gray-600">
                Constantly evolving with the latest agricultural technology
              </p>
            </div>
            <div className="text-center">
              <div className="bg-green-100 w-16 h-16 rounded-full flex items-center justify-center mx-auto mb-4">
                <Award className="h-8 w-8 text-green-600" />
              </div>
              <h3 className="text-xl font-semibold mb-2">Sustainability</h3>
              <p className="text-gray-600">
                Promoting practices that benefit both farmers and the environment
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="bg-green-600 text-white py-16">
        <div className="container mx-auto px-4 text-center">
          <h2 className="text-3xl font-bold mb-4">Join the Krishimitra Community</h2>
          <p className="text-xl mb-8">Start making smarter farming decisions today</p>
          <Button size="lg" variant="secondary" onClick={() => navigate("/auth")}>
            Get Started Free
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

export default About;
