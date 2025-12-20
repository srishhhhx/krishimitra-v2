import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Checkbox } from "@/components/ui/checkbox";
import { useToast } from "@/hooks/use-toast";
import { Sprout } from "lucide-react";

const Auth = () => {
  const navigate = useNavigate();
  const { toast } = useToast();
  const [loading, setLoading] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [farmSize, setFarmSize] = useState("");
  const [selectedCrops, setSelectedCrops] = useState<string[]>([]);
  const API_BASE = import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000";
  const cropGroups: { label: string; items: string[] }[] = [
    { label: "Cereals", items: ["Rice (Paddy)", "Wheat", "Maize (Corn)", "Barley", "Sorghum (Jowar)", "Millet (Bajra, Ragi)", "Oats"] },
    { label: "Pulses/Legumes", items: ["Chickpea (Gram)", "Lentils (Masoor)", "Black Gram (Urad)", "Green Gram (Moong)", "Pigeon Pea (Tur/Arhar)", "Soybean", "Peas"] },
    { label: "Oilseed Crops", items: ["Groundnut (Peanut)", "Mustard / Rapeseed", "Sunflower", "Sesame (Til)", "Soybean (dual-purpose)", "Coconut (for oil extraction)"] },
    { label: "Cash / Plantation Crops", items: ["Sugarcane", "Cotton", "Tea", "Coffee", "Rubber", "Tobacco"] },
    { label: "Vegetables", items: ["Tomato", "Onion", "Potato", "Carrot", "Cabbage / Cauliflower / Broccoli", "Brinjal (Eggplant)", "Capsicum / Bell Pepper", "Cucumber", "Spinach / Leafy greens"] },
    { label: "Fruits", items: ["Mango", "Banana", "Apple", "Orange / Citrus", "Grapes", "Pomegranate", "Papaya", "Guava", "Watermelon / Melons"] },
  ];

  useEffect(() => {
    const token = localStorage.getItem("access_token");
    if (token) {
      navigate("/dashboard");
    }
  }, [navigate]);

  const handleSignUp = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    // Basic client-side validation to reduce 422s
    if (!farmSize) {
      toast({ title: "Error", description: "Please select a farm size.", variant: "destructive" });
      setLoading(false);
      return;
    }
    if (selectedCrops.length === 0) {
      toast({ title: "Error", description: "Please select at least one primary crop.", variant: "destructive" });
      setLoading(false);
      return;
    }
    const hasLetter = /[A-Za-z]/.test(password);
    const hasDigit = /\d/.test(password);
    if (password.length < 8 || !hasLetter || !hasDigit) {
      toast({ title: "Error", description: "Password must be at least 8 characters and include letters and numbers.", variant: "destructive" });
      setLoading(false);
      return;
    }
    try {
      const res = await fetch(`${API_BASE}/auth/signup`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "Accept": "application/json" },
        body: JSON.stringify({
          email,
          password,
          full_name: fullName,
          farm_size: farmSize,
          primary_crops: selectedCrops,
          // The backend model may include additional optional fields like phone_number/state/etc.
          // If those are required, we will extend this form once confirmed.
        }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        if (res.status === 422 && Array.isArray(data?.detail)) {
          const msg = data.detail.map((d: any) => `${d?.loc?.slice(-1)[0] || "field"}: ${d?.msg || "invalid"}`).join("; ");
          throw new Error(msg);
        }
        throw new Error(data.detail || "Signup failed");
      }
      toast({
        title: "Success!",
        description: "Account created successfully. You can now sign in.",
      });
    } catch (err: any) {
      toast({
        title: "Error",
        description: err.message || "Signup failed",
        variant: "destructive",
      });
    }
    setLoading(false);
  };

  const handleSignIn = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "Accept": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        if (res.status === 422 && Array.isArray(data?.detail)) {
          const msg = data.detail.map((d: any) => `${d?.loc?.slice(-1)[0] || "field"}: ${d?.msg || "invalid"}`).join("; ");
          throw new Error(msg);
        }
        throw new Error(data.detail || "Login failed");
      }
      if (data?.access_token) {
        localStorage.setItem("access_token", data.access_token);
        navigate("/dashboard");
      } else {
        throw new Error("No access token returned");
      }
    } catch (err: any) {
      toast({
        title: "Error",
        description: err.message || "Login failed",
        variant: "destructive",
      });
    }
    setLoading(false);
  };

  return (
    <div className="min-h-screen bg-gradient-to-b from-green-50 to-white flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <div className="flex items-center justify-center gap-2 mb-4">
            <Sprout className="h-10 w-10 text-green-600" />
            <span className="text-3xl font-bold text-green-800">Krishimitra</span>
          </div>
          <p className="text-gray-600">Welcome to smart agriculture</p>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>Authentication</CardTitle>
            <CardDescription>Sign in or create an account to get started</CardDescription>
          </CardHeader>
          <CardContent>
            <Tabs defaultValue="signin">
              <TabsList className="grid w-full grid-cols-2">
                <TabsTrigger value="signin">Sign In</TabsTrigger>
                <TabsTrigger value="signup">Sign Up</TabsTrigger>
              </TabsList>

              <TabsContent value="signin">
                <form onSubmit={handleSignIn} className="space-y-4">
                  <div className="space-y-2">
                    <Label htmlFor="signin-email">Email</Label>
                    <Input
                      id="signin-email"
                      type="email"
                      placeholder="you@example.com"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      required
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="signin-password">Password</Label>
                    <Input
                      id="signin-password"
                      type="password"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      required
                    />
                  </div>
                  <Button type="submit" className="w-full" disabled={loading}>
                    {loading ? "Signing in..." : "Sign In"}
                  </Button>
                </form>
              </TabsContent>

              <TabsContent value="signup">
                <form onSubmit={handleSignUp} className="space-y-4">
                  <div className="space-y-2">
                    <Label htmlFor="signup-name">Full Name</Label>
                    <Input
                      id="signup-name"
                      type="text"
                      placeholder="Your name"
                      value={fullName}
                      onChange={(e) => setFullName(e.target.value)}
                      required
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="signup-email">Email</Label>
                    <Input
                      id="signup-email"
                      type="email"
                      placeholder="you@example.com"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      required
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="signup-password">Password</Label>
                    <Input
                      id="signup-password"
                      type="password"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      required
                      minLength={8}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="signup-farm-size">Farm Size</Label>
                    <Select value={farmSize} onValueChange={(v) => setFarmSize(v)}>
                      <SelectTrigger id="signup-farm-size">
                        <SelectValue placeholder="Select farm size" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="small">Small</SelectItem>
                        <SelectItem value="medium">Medium</SelectItem>
                        <SelectItem value="large">Large</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-2">
                    <Label>Primary Crops</Label>
                    <div className="space-y-3 max-h-60 overflow-auto border rounded-md p-3">
                      {cropGroups.map((group) => (
                        <div key={group.label} className="space-y-2">
                          <div className="text-sm font-medium text-gray-700">{group.label}</div>
                          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                            {group.items.map((item) => {
                              const checked = selectedCrops.includes(item);
                              return (
                                <label key={item} className="flex items-center gap-2 text-sm">
                                  <Checkbox
                                    checked={checked}
                                    onCheckedChange={(v) => {
                                      setSelectedCrops((prev) => {
                                        const isChecked = Boolean(v);
                                        if (isChecked) return Array.from(new Set([...prev, item]));
                                        return prev.filter((x) => x !== item);
                                      });
                                    }}
                                  />
                                  <span>{item}</span>
                                </label>
                              );
                            })}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                  <Button type="submit" className="w-full" disabled={loading}>
                    {loading ? "Creating account..." : "Sign Up"}
                  </Button>
                </form>
              </TabsContent
>
            </Tabs>

            <div className="mt-4 text-center">
              <Button variant="link" onClick={() => navigate("/")}>
                Back to Home
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default Auth;
