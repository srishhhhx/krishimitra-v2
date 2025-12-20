
import React, { useState } from "react";
import { Search, Menu, Bell, X, LogOut } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";
import { cn } from "@/lib/utils";
import { useTranslation } from "react-i18next";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useToast } from "@/hooks/use-toast";
import i18n from "@/i18n";
import KrishiLogo from "./KrishiLogo";

interface NavbarProps {
  location: string;
  setLocation: (location: string) => void;
}

const Navbar: React.FC<NavbarProps> = ({ location, setLocation }) => {
  const [searchValue, setSearchValue] = useState(location);
  const [isSearchOpen, setIsSearchOpen] = useState(false);
  const { t } = useTranslation();
  const { toast } = useToast();
  const navigate = useNavigate();
  const currentLang = (i18n.language || 'en').split('-')[0];

  const handleLogout = async () => {
    try {
      localStorage.removeItem("access_token");
      navigate("/");
    } catch (err: any) {
      toast({
        title: "Error",
        description: err?.message || "Logout failed",
        variant: "destructive",
      });
    }
  };

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setLocation(searchValue);
    setIsSearchOpen(false);
  };

  return (
    <nav className="bg-white border-b border-gray-200 sticky top-0 z-50">
      <div className="container mx-auto px-4">
        <div className="flex justify-between items-center h-16">
          {/* Logo */}
          <div className="flex items-center">
            <div className="flex items-center gap-3">
              <KrishiLogo size="md" variant="default" />
              <span className="text-xl font-bold text-agro-green-dark">
                {t('brand')}
              </span>
            </div>
          </div>

          {/* Desktop Navigation */}
          <div className="hidden md:flex md:items-center md:space-x-4">
            <form onSubmit={handleSearch} className="relative w-64">
              <Input
                type="text"
                placeholder={t('search_location')}
                value={searchValue}
                onChange={(e) => setSearchValue(e.target.value)}
                className="pr-10"
              />
              <Button
                type="submit"
                variant="ghost"
                size="icon"
                className="absolute right-0 top-0 h-full"
              >
                <Search className="h-4 w-4" />
              </Button>
            </form>
            <Button variant="ghost" size="icon">
              <Bell className="h-5 w-5" />
            </Button>
            <div className="w-36">
              <Select value={currentLang} onValueChange={(lng) => i18n.changeLanguage(lng)}>
                <SelectTrigger aria-label={t('lang.label')}>
                  <SelectValue placeholder={t('lang.label')} />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="en">{t('lang.en')}</SelectItem>
                  <SelectItem value="hi">{t('lang.hi')}</SelectItem>
                  <SelectItem value="mr">{t('lang.mr')}</SelectItem>
                  <SelectItem value="bn">{t('lang.bn')}</SelectItem>
                  <SelectItem value="te">{t('lang.te')}</SelectItem>
                  <SelectItem value="ta">{t('lang.ta')}</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <Button variant="ghost" size="icon" onClick={handleLogout} title="Logout">
              <LogOut className="h-5 w-5" />
            </Button>
          </div>

          {/* Mobile Search Toggle */}
          <div className="flex md:hidden items-center space-x-2">
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setIsSearchOpen(!isSearchOpen)}
            >
              {isSearchOpen ? (
                <X className="h-5 w-5" />
              ) : (
                <Search className="h-5 w-5" />
              )}
            </Button>
            <Button variant="ghost" size="icon">
              <Bell className="h-5 w-5" />
            </Button>
            
            <Sheet>
              <SheetTrigger asChild>
                <Button variant="ghost" size="icon" className="md:hidden">
                  <Menu className="h-5 w-5" />
                </Button>
              </SheetTrigger>
              <SheetContent side="left">
                <div className="py-4">
                  <h2 className="text-xl font-bold text-agro-green-dark mb-4">
                    {t('brand')}
                  </h2>
                  <div className="space-y-3">
                    <button className="block w-full text-left px-4 py-2 rounded-md hover:bg-gray-100">{t('nav.dashboard')}</button>
                    <button className="block w-full text-left px-4 py-2 rounded-md hover:bg-gray-100">{t('nav.disease_detection')}</button>
                    <button className="block w-full text-left px-4 py-2 rounded-md hover:bg-gray-100">{t('nav.fertilizer_advisor')}</button>
                    <button className="block w-full text-left px-4 py-2 rounded-md hover:bg-gray-100">{t('nav.local_advisory')}</button>
                    <button className="block w-full text-left px-4 py-2 rounded-md hover:bg-gray-100">{t('nav.settings')}</button>
                  </div>
                  <div className="mt-4">
                    <label className="text-sm text-gray-600">{t('lang.label')}</label>
                    <div className="mt-2">
                      <Select value={currentLang} onValueChange={(lng) => i18n.changeLanguage(lng)}>
                        <SelectTrigger>
                          <SelectValue placeholder={t('lang.label')} />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="en">{t('lang.en')}</SelectItem>
                          <SelectItem value="hi">{t('lang.hi')}</SelectItem>
                          <SelectItem value="mr">{t('lang.mr')}</SelectItem>
                          <SelectItem value="bn">{t('lang.bn')}</SelectItem>
                          <SelectItem value="te">{t('lang.te')}</SelectItem>
                          <SelectItem value="ta">{t('lang.ta')}</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                  </div>
                  <div className="mt-4">
                    <Button 
                      variant="outline" 
                      className="w-full" 
                      onClick={handleLogout}
                    >
                      <LogOut className="h-4 w-4 mr-2" />
                      Logout
                    </Button>
                  </div>
                </div>
              </SheetContent>
            </Sheet>
          </div>
        </div>

        {/* Mobile Search Bar */}
        <div
          className={cn(
            "pb-3 md:hidden",
            isSearchOpen ? "block" : "hidden"
          )}
        >
          <form onSubmit={handleSearch} className="relative">
            <Input
              type="text"
              placeholder={t('search_location')}
              value={searchValue}
              onChange={(e) => setSearchValue(e.target.value)}
              className="pr-10"
            />
            <Button
              type="submit"
              variant="ghost"
              size="icon"
              className="absolute right-0 top-0 h-full"
            >
              <Search className="h-4 w-4" />
            </Button>
          </form>
        </div>
      </div>
    </nav>
  );
};

export default Navbar;
