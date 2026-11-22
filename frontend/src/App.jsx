import React, { useEffect, useState } from 'react';
import { Utensils, ArrowLeft, Clock, Users, Flame, ChevronRight, Play, CheckCircle2, Sparkles } from 'lucide-react';

const CUISINES = ['Indian', 'Mexican', 'Italian', 'Japanese', 'Mediterranean', 'Thai'];
const DIETARY_OPTIONS = ['Vegetarian', 'Vegan', 'Gluten-Free', 'Pescatarian', 'Dairy-Free'];

function App() {
  // 🚀 FIXED: Standardized view management states
  const [currentView, setCurrentView] = useState("cuisines"); // "cuisines" | "dashboard" | "menu_options" | "recipe"
  const [selectedCuisine, setSelectedCuisine] = useState('');
  const [selectedDiet, setSelectedDiet] = useState([]);
  const [triedFavorites, setTriedFavorites] = useState([]);
  const [savedFavorites, setSavedFavorites] = useState([]);
  const [isSaved, setIsSaved] = useState(false);
  const [isTried, setIsTried] = useState(false);
  const [token, setToken] = useState(() => localStorage.getItem('recipe_profile_token') || '');
  const [profile, setProfile] = useState(null);
  const [usernameInput, setUsernameInput] = useState('');
  const [loginError, setLoginError] = useState(null);
  const [loggingIn, setLoggingIn] = useState(false);
  const [checkingSession, setCheckingSession] = useState(Boolean(localStorage.getItem('recipe_profile_token')));
  
  // API Return Cache States
  const [menuOptions, setMenuOptions] = useState([]);
  const [selectedDish, setSelectedDish] = useState('');
  const [recipeRestrictions, setRecipeRestrictions] = useState([]);
  const [recipeDetails, setRecipeDetails] = useState(null);
  const [mediaLinks, setMediaLinks] = useState(null);
  
  // UI UX Polish States
  const [loading, setLoading] = useState(false);
  const [menuError, setMenuError] = useState(null);
  const [recipeError, setRecipeError] = useState(null);
  const [actionError, setActionError] = useState(null);

  const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

  // Fetch and validate API responses before handing data to React components.
  // 4xx/5xx response bodies often contain { detail: ... }, not menu_options.
  const fetchJson = async (path, payload, anonymous = false) => {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token && !anonymous ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify(payload),
    });
    let data;
    try {
      data = await response.json();
    } catch {
      throw new Error(`Server returned a non-JSON response (HTTP ${response.status}).`);
    }
    if (!response.ok) {
      // Avoid showing raw backend stack traces or internal exceptions to users.
      throw new Error(`Request failed (HTTP ${response.status}). Please retry.`);
    }
    return data;
  };

  useEffect(() => {
    const stored = localStorage.getItem('recipe_profile_token');
    if (!stored) return;
    fetch(`${API_BASE_URL}/api/session`, {
      headers: { Authorization: `Bearer ${stored}` },
    }).then(async response => {
      if (!response.ok) throw new Error('Session expired');
      return response.json();
    }).then(setProfile).catch(() => {
      localStorage.removeItem('recipe_profile_token');
      setToken('');
    }).finally(() => setCheckingSession(false));
  }, [API_BASE_URL]);

  const login = async (event) => {
    event.preventDefault();
    setLoginError(null);
    setLoggingIn(true);
    try {
      const data = await fetchJson('/api/session', { username: usernameInput.trim() }, true);
      if (!data.token || !data.username || !data.user_id) throw new Error('Invalid profile response');
      localStorage.setItem('recipe_profile_token', data.token);
      setToken(data.token);
      setProfile({ username: data.username, user_id: data.user_id });
      setCurrentView('cuisines');
    } catch (error) {
      setLoginError(error instanceof Error ? error.message : 'Could not start a profile.');
    } finally {
      setLoggingIn(false);
    }
  };

  const logout = async () => {
    if (token) {
      fetch(`${API_BASE_URL}/api/session`, {
        method: 'DELETE', headers: { Authorization: `Bearer ${token}` },
      }).catch(() => {});
    }
    localStorage.removeItem('recipe_profile_token');
    setToken('');
    setProfile(null);
    setUsernameInput('');
    setSelectedCuisine('');
    setMenuOptions([]);
    setTriedFavorites([]);
    setSavedFavorites([]);
    setRecipeDetails(null);
    setMediaLinks(null);
    setCurrentView('cuisines');
  };

  const updateRecipeAction = async (action, active) => {
    setActionError(null);
    try {
      await fetchJson('/api/recipe-action', {
        selected_dish: selectedDish,
        cuisine: selectedCuisine,
        dietary_restrictions: recipeRestrictions,
        action, active,
      });
      if (action === 'saved') setIsSaved(active);
      else setIsTried(active);
    } catch (error) {
      setActionError(error instanceof Error ? error.message : 'Failed to update recipe.');
    }
  };

  const toggleDietary = (diet) => {
    setSelectedDiet(prev => 
      prev.includes(diet) ? prev.filter(d => d !== diet) : [...prev, diet]
    );
  };

  const refreshDashboardHistory = async (cuisineName) => {
    try {
      const data = await fetchJson('/api/menu-dashboard', {
        cuisine: cuisineName,
        dietary_restrictions: selectedDiet,
      });
      const favorites = Array.isArray(data.previously_tried) ? data.previously_tried : [];
      const saved = Array.isArray(data.saved_favorites) ? data.saved_favorites : [];
      setTriedFavorites(favorites);
      setSavedFavorites(saved);
      return favorites.length > 0 || saved.length > 0;
    } catch (err) {
      console.error('Error refreshing dashboard state:', err);
      setTriedFavorites([]);
      setSavedFavorites([]);
      // A history failure should not prevent fresh menu discovery.
      return false;
    }
  };

  // 🚀 NEW: Checks history state to choose whether to display the split dashboard
  const handleCuisineSelect = async (cuisine) => {
    setSelectedCuisine(cuisine);
    setLoading(true);
    const hasHistory = await refreshDashboardHistory(cuisine);
    setLoading(false);
    
    if (hasHistory) {
      setMenuOptions([]); 
      setCurrentView("dashboard");
    } else {
      await triggerAiMenuGeneration(cuisine);
    }
  };

  // 🚀 MODIFIED: The original Phase 1 loop is now explicitly bound to the Exploration Column
  const triggerAiMenuGeneration = async (cuisineName) => {
    setLoading(true);
    setMenuError(null);
    setMenuOptions([]);
    setCurrentView('menu_options');
    try {
      const data = await fetchJson('/api/menu', {
        cuisine: cuisineName,
        dietary_restrictions: selectedDiet,
      });
      if (!Array.isArray(data.menu_options) || data.menu_options.length === 0) {
        throw new Error('No menu suggestions were returned. Please try again.');
      }
      setMenuOptions(data.menu_options);
    } catch (err) {
      console.error('Error fetching menu options:', err);
      setMenuError(err instanceof Error ? err.message : 'Unable to load menu suggestions.');
    } finally {
      setLoading(false);
    }
  };

  // Phase 2: Call Backend to trigger concurrent Chef + Media assembly nodes
  const fetchRecipe = async (dishName, restrictions = selectedDiet) => {
    setSelectedDish(dishName);
    setRecipeRestrictions([...restrictions]);
    setRecipeDetails(null);
    setRecipeError(null);
    setActionError(null);
    setIsSaved(false);
    setIsTried(false);
    setLoading(true);
    setCurrentView('recipe');
    try {
      const data = await fetchJson('/api/recipe', {
        selected_dish: dishName,
        dietary_restrictions: restrictions,
        cuisine: selectedCuisine,
      });
      if (!data.recipe_details || !Array.isArray(data.recipe_details.ingredients) ||
          !Array.isArray(data.recipe_details.instructions)) {
        throw new Error('The server returned incomplete recipe details. Please retry.');
      }
      setRecipeDetails(data.recipe_details);
      setMediaLinks(data.media_links);
      setIsSaved(Boolean(data.is_saved));
      setIsTried(Boolean(data.is_tried));
    } catch (err) {
      console.error('Error fetching recipe details:', err);
      setRecipeError(err instanceof Error ? err.message : 'Unable to load this recipe.');
    } finally {
      setLoading(false);
    }
  };

  if (checkingSession) return (
    <div className="mx-auto max-w-lg p-10 text-center text-slate-600">Restoring your profile...</div>
  );

  if (!profile) return (
    <div className="mx-auto max-w-md px-4 py-16">
      <div className="rounded-3xl border border-slate-200 bg-white p-8 shadow-sm space-y-5">
        <h1 className="text-3xl font-extrabold text-indigo-700">What Should I Eat?</h1>
        <h2 className="text-xl font-semibold">Choose a username</h2>
        <p className="text-sm text-slate-600">Start a profile to keep your saved and tried recipes separate in this browser.</p>
        <form onSubmit={login} className="space-y-3">
          <label htmlFor="username" className="block text-sm font-semibold text-slate-700">Username</label>
          <input id="username" autoComplete="nickname" required minLength={3} maxLength={24}
            pattern="[A-Za-z0-9_]{3,24}" value={usernameInput}
            onChange={event => setUsernameInput(event.target.value)}
            placeholder="e.g. home_chef" className="w-full rounded-xl border border-slate-300 px-4 py-3 focus:outline-indigo-500" />
          {loginError && <p role="alert" className="text-sm text-red-600">{loginError}</p>}
          <button type="submit" disabled={loggingIn}
            className="w-full rounded-xl bg-indigo-600 p-3 font-semibold text-white disabled:opacity-60">
            {loggingIn ? 'Creating profile...' : 'Continue'}
          </button>
        </form>
        <p className="text-xs text-amber-800">Demo profiles are browser-bound, not password-protected accounts. Clearing browser data or switching devices loses access to this profile. Don't store sensitive information.</p>
      </div>
    </div>
  );

  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      {/* Header Layout */}
      <header className="flex items-center gap-3 mb-10 pb-6 border-b border-slate-200">
        <Utensils className="h-8 w-8 text-indigo-600" />
        <h1 className="text-3xl font-extrabold tracking-tight bg-gradient-to-r from-indigo-600 to-violet-600 bg-clip-text text-transparent">
          What Should I Eat?
        </h1>
        <div className="ml-auto flex items-center gap-3">
          <span className="text-xs font-semibold text-slate-600">@{profile.username}</span>
          <button onClick={logout} className="rounded-lg border border-slate-200 px-3 py-2 text-xs text-slate-600 hover:bg-slate-100">Sign out</button>
        </div>
      </header>

      {/* VIEW 1: SELECT CUISINE & PREFERENCES */}
      {currentView === "cuisines" && (
        <div className="space-y-8 animate-fadeIn">
          <div>
            <h2 className="text-xl font-semibold mb-3">Any dietary restrictions?</h2>
            <div className="flex gap-3">
              {DIETARY_OPTIONS.map(diet => (
                <button
                  key={diet}
                  onClick={() => toggleDietary(diet)}
                  className={`px-4 py-2 rounded-full border text-sm font-medium transition-all ${
                    selectedDiet.includes(diet)
                      ? 'bg-indigo-600 text-white border-indigo-600 shadow-sm'
                      : 'bg-white text-slate-700 border-slate-200 hover:border-slate-300'
                  }`}
                >
                  {diet}
                </button>
              ))}
            </div>
          </div>

          <div>
            <h2 className="text-xl font-semibold mb-4">What cuisine are you craving for dinner?</h2>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
              {CUISINES.map(cuisine => (
                <button
                  key={cuisine}
                  onClick={() => handleCuisineSelect(cuisine)} // 🚀 FIXED: Routed to historical router hook
                  className="p-6 text-left bg-white border border-slate-200 rounded-xl hover:border-indigo-500 hover:shadow-md transition-all group"
                >
                  <span className="text-lg font-bold group-hover:text-indigo-600 transition-colors block mb-1">
                    {cuisine}
                  </span>
                  <span className="text-xs text-slate-400 flex items-center gap-1">
                    Explore items <ChevronRight className="h-3 w-3" />
                  </span>
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* 🚀 BRAND NEW VIEW: THE SPLIT-SCREEN MENU DASHBOARD */}
      {currentView === "dashboard" && (
        <div className="space-y-6 animate-fadeIn">
          <div className="flex items-center justify-between border-b border-slate-100 pb-4">
            <h2 className="text-2xl font-black text-slate-800 capitalize">🍳 Explore {selectedCuisine} Cuisine</h2>
            <button 
              onClick={() => setCurrentView("cuisines")}
              className="flex items-center gap-1 text-xs font-semibold px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-600 rounded-xl transition"
            >
              <ArrowLeft className="h-3 w-3" /> Back
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {savedFavorites.length > 0 && (
              <div className="md:col-span-2 rounded-2xl border border-emerald-100 bg-emerald-50 p-5">
                <h3 className="mb-3 text-sm font-bold text-emerald-800">Saved recipes</h3>
                <div className="flex flex-wrap gap-2">
                  {savedFavorites.map((dish, index) => (
                    <button key={index} onClick={() => fetchRecipe(dish.dish_name, dish.dietary_restrictions)}
                      className="rounded-lg border border-emerald-200 bg-white px-3 py-2 text-xs font-semibold hover:border-emerald-500">
                      {dish.dish_name}
                    </button>
                  ))}
                </div>
              </div>
            )}
            {/* Left Column: Premium History Cards */}
            <div className="bg-slate-50 border border-slate-200/70 rounded-2xl p-5 space-y-4 shadow-xs">
              <div>
                <h3 className="text-sm font-black text-indigo-600 uppercase tracking-wider flex items-center gap-1.5">
                  <CheckCircle2 className="h-4 w-4 text-indigo-500" /> Marked as Tried
                </h3>
                <p className="text-[11px] text-slate-400 mt-0.5">Only recipes you explicitly marked as tried</p>
              </div>
              
              <div className="space-y-3">
                {triedFavorites.map((dish, i) => (
                  <div
                    key={i}
                    onClick={() => fetchRecipe(dish.dish_name, dish.dietary_restrictions)} // Fetch the specific stored recipe variant
                    className="group bg-white p-4 rounded-xl border border-slate-100 shadow-2xs cursor-pointer hover:border-indigo-500 hover:shadow-sm transition-all flex justify-between items-start"
                  >
                    <div className="space-y-1 pr-4">
                      <div className="flex items-center gap-1.5">
                        <h4 className="text-sm font-bold text-slate-800 group-hover:text-indigo-600 transition-colors">{dish.dish_name}</h4>
                        <span className="text-[9px] px-1.5 py-0.5 bg-emerald-50 text-emerald-600 rounded font-bold">⚡ 10ms</span>
                      </div>
                      <p className="text-xs text-slate-500 line-clamp-2 leading-relaxed">{dish.teaser}</p>
                    </div>
                    <div className="text-right flex-shrink-0 space-y-1">
                      <div className="text-[10px] text-slate-400 font-medium">{dish.prep_time}</div>
                      <div className="text-[10px] px-1.5 py-0.5 bg-slate-100 text-slate-500 rounded font-bold capitalize">{dish.difficulty}</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* 🚀 RIGHT COLUMN: Innovation & Action Target Block */}
            <div className="bg-slate-50 border border-slate-200/70 rounded-2xl p-5 flex flex-col shadow-xs min-h-[350px]">
              <div>
                <h3 className="text-sm font-black text-amber-600 uppercase tracking-wider flex items-center gap-1.5">
                  <Sparkles className="h-4 w-4 text-amber-500" /> Something Brand New
                </h3>
                <p className="text-[11px] text-slate-400 mt-0.5">Activate your multi-model AI agent mesh to discover flavors</p>
              </div>

              {/* CONDITIONAL RENDER: If no choices are generated yet, show the Magic Wand Button */}
              {menuOptions.length === 0 ? (
                <div className="flex-1 flex flex-col items-center justify-center text-center p-6 my-4 bg-white rounded-2xl border border-dashed border-slate-200">
                  <span className="text-3xl mb-2">🪄</span>
                  <h4 className="text-sm font-bold text-slate-700">Ready for a fresh creation?</h4>
                  <p className="text-xs text-slate-400 max-w-xs mt-1 mb-4">Click below to query your agent network for five customized culinary recommendations.</p>
                  <button
                    onClick={() => triggerAiMenuGeneration(selectedCuisine)}
                    className="px-5 py-2.5 text-xs font-bold text-white bg-amber-500 hover:bg-amber-600 rounded-xl shadow-sm transition transform active:scale-98"
                  >
                    {loading ? "Curation in progress..." : "Generate 5 Fresh Options"}
                  </button>
                </div>
              ) : (
                /* IF OPTIONS EXIST: Render them right here inside the dashboard panel! */
                <div className="mt-4 flex-1 space-y-2 overflow-y-auto">
                  <h4 className="text-[10px] font-black text-slate-400 uppercase tracking-wider mb-2">✨ Curated AI Recommendations:</h4>
                  {menuOptions.map((dish, idx) => (
                    <div 
                      key={idx}
                      onClick={() => fetchRecipe(dish.dish_name)}
                      className="p-3.5 bg-white border border-slate-100 rounded-xl hover:border-amber-500 hover:shadow-xs cursor-pointer transition-all flex justify-between items-center group"
                    >
                      <div className="space-y-0.5 max-w-[90%]">
                        <h4 className="text-xs font-bold text-slate-800 group-hover:text-amber-600 transition-colors">{dish.dish_name}</h4>
                        <p className="text-slate-500 text-[11px] line-clamp-1 leading-normal">{dish.teaser}</p>
                      </div>
                      <ChevronRight className="h-3 w-3 text-slate-300 group-hover:text-amber-500 transform group-hover:translate-x-0.5 transition-all flex-shrink-0" />
                    </div>
                  ))}
                  
                  {/* Optional Reset Button to clear and generate again */}
                  <button 
                    onClick={() => setMenuOptions([])}
                    className="w-full text-center text-[10px] font-bold text-slate-400 hover:text-slate-600 mt-2 transition"
                  >
                    Clear & Regenerate Options
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* VIEW 2: DISPLAY 5 AI RECIPE OPTIONS */}
      {currentView === "menu_options" && (
        <div className="space-y-6 animate-fadeIn">
          <button 
            onClick={() => setCurrentView(triedFavorites.length > 0 ? "dashboard" : "cuisines")} 
            className="flex items-center gap-2 text-sm font-medium text-slate-500 hover:text-slate-800 transition-colors"
          >
            <ArrowLeft className="h-4 w-4" /> Back
          </button>
          
          <h2 className="text-2xl font-bold">5 Handpicked {selectedCuisine} Options</h2>

          {loading ? (
            <div className="space-y-3">
              {[...Array(5)].map((_, i) => (
                <div key={i} className="h-24 bg-slate-200 animate-pulse rounded-xl" />
              ))}
            </div>
          ) : menuError ? (
            <div role="alert" className="rounded-xl border border-red-200 bg-red-50 p-6 space-y-3">
              <h3 className="font-bold text-red-900">Couldn't load menu suggestions</h3>
              <p className="text-sm text-red-800">{menuError}</p>
              <div className="flex flex-wrap gap-3">
                <button onClick={() => triggerAiMenuGeneration(selectedCuisine)} className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white">Retry</button>
                <button onClick={() => setCurrentView('cuisines')} className="rounded-lg border border-slate-300 px-4 py-2 text-sm">Choose another cuisine</button>
              </div>
            </div>
          ) : (
            <div className="space-y-3">
              {menuOptions.map((dish, idx) => (
                <div 
                  key={idx}
                  onClick={() => fetchRecipe(dish.dish_name)}
                  className="p-5 bg-white border border-slate-200 rounded-xl hover:border-indigo-500 hover:shadow-sm cursor-pointer transition-all flex justify-between items-center group"
                >
                  <div className="space-y-1 max-w-[85%]">
                    <h3 className="text-lg font-bold group-hover:text-indigo-600 transition-colors">{dish.dish_name}</h3>
                    <p className="text-slate-600 text-sm leading-relaxed">{dish.teaser}</p>
                    <span className="inline-block bg-slate-100 text-slate-600 text-xs px-2 py-0.5 rounded font-medium">
                      Protein Base: {dish.primary_protein}
                    </span>
                  </div>
                  <ChevronRight className="h-5 w-5 text-slate-300 group-hover:text-indigo-500 transform group-hover:translate-x-1 transition-all" />
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* VIEW 3: FULL RECIPE DETAILS & RICH MEDIA ASSISTANT */}
      {currentView === "recipe" && (
        <div className="space-y-6 animate-fadeIn">
          <button 
            onClick={async () => {
              setLoading(true);
              // 🚀 FORCE RE-SYNC: Pull the item we just cooked straight from Redis Cloud
              await refreshDashboardHistory(selectedCuisine);
              setLoading(false);
              setCurrentView("dashboard");
            }}
            className="flex items-center gap-2 text-sm font-medium text-slate-500 hover:text-slate-800 transition-colors"
          >
            <ArrowLeft className="h-4 w-4" /> Back to Menu Dashboard
          </button>

          {loading ? (
            <div className="space-y-4 animate-pulse">
              <div className="h-48 bg-slate-200 rounded-xl" />
              <div className="h-8 bg-slate-200 w-1/3 rounded" />
              <div className="h-24 bg-slate-200 rounded-xl" />
            </div>
          ) : recipeError || !recipeDetails ? (
            <div role="alert" className="rounded-xl border border-red-200 bg-red-50 p-6 space-y-3">
              <h3 className="font-bold text-red-900">Couldn't load this recipe</h3>
              <p className="text-sm text-red-800">{recipeError || 'No recipe details were returned.'}</p>
              <button onClick={() => fetchRecipe(selectedDish, recipeRestrictions)} className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white">Retry recipe</button>
            </div>
          ) : (
            <div className="space-y-8">
              {recipeRestrictions.length > 0 && (
                <p role="note" className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900">
                  Requested restrictions: {recipeRestrictions.join(', ')}. AI-generated recipes are screened for obvious ingredient conflicts, but dietary suitability,
                  allergens, product labels, and cross-contact are not verified. Check all ingredients before cooking.
                </p>
              )}
              {actionError && <p role="alert" className="rounded-lg bg-red-50 p-3 text-sm text-red-700">{actionError}</p>}
              <div className="flex flex-wrap gap-3">
                <button type="button" onClick={() => updateRecipeAction('saved', !isSaved)}
                  className={`rounded-xl border px-4 py-2 text-sm font-semibold ${isSaved ? 'border-emerald-600 bg-emerald-50 text-emerald-800' : 'border-slate-200 bg-white text-slate-700'}`}>
                  {isSaved ? 'Saved ✓ · Unsave' : '☆ Save recipe'}
                </button>
                <button type="button" onClick={() => updateRecipeAction('tried', !isTried)}
                  className={`rounded-xl border px-4 py-2 text-sm font-semibold ${isTried ? 'border-indigo-600 bg-indigo-50 text-indigo-800' : 'border-slate-200 bg-white text-slate-700'}`}>
                  {isTried ? 'Tried ✓ · Unmark' : '✓ Mark as tried'}
                </button>
              </div>
              {/* Cover Card Banner */}
              <div 
                className="relative h-64 w-full bg-cover bg-center rounded-2xl shadow-inner flex items-end p-6 overflow-hidden border border-slate-200"
                style={{ backgroundImage: `url(${mediaLinks?.image_url})` }}
              >
                <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-black/40 to-transparent" />
                <h2 className="relative text-3xl font-black text-white">{recipeDetails.dish_name}</h2>
              </div>

              {/* Quick Spec Metadata Row */}
              <div className="grid grid-cols-3 gap-4 p-4 bg-white border border-slate-200 rounded-xl text-center shadow-sm">
                <div className="flex flex-col items-center gap-1 border-r border-slate-100">
                  <Clock className="h-5 w-5 text-indigo-500" />
                  <span className="text-xs text-slate-400 font-medium uppercase tracking-wider">Prep Time</span>
                  <span className="text-sm font-semibold">{recipeDetails.prep_time}</span>
                </div>
                <div className="flex flex-col items-center gap-1 border-r border-slate-100">
                  <Flame className="h-5 w-5 text-orange-500" />
                  <span className="text-xs text-slate-400 font-medium uppercase tracking-wider">Cook Time</span>
                  <span className="text-sm font-semibold">{recipeDetails.cook_time}</span>
                </div>
                <div className="flex flex-col items-center gap-1">
                  <Users className="h-5 w-5 text-emerald-500" />
                  <span className="text-xs text-slate-400 font-medium uppercase tracking-wider">Servings</span>
                  <span className="text-sm font-semibold">{recipeDetails.servings}</span>
                </div>
              </div>

              {/* Core Execution Columns */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
                {/* Left Side: Ingredients */}
                <div className="md:col-span-1 bg-white border border-slate-200 p-6 rounded-2xl shadow-sm h-fit">
                  <h3 className="text-lg font-bold mb-4 pb-2 border-b border-slate-100">Ingredients</h3>
                  <ul className="space-y-3">
                    {recipeDetails.ingredients.map((item, index) => (
                      <li key={index} className="text-sm text-slate-600 leading-normal flex gap-2 items-start">
                        <span className="text-indigo-500 font-bold">•</span>
                        <span>{item}</span>
                      </li>
                    ))}
                  </ul>
                </div>

                {/* Right Side: Step-by-Step Instructions */}
                <div className="md:col-span-2 space-y-6">
                  <div className="bg-white border border-slate-200 p-6 rounded-2xl shadow-sm">
                    <h3 className="text-lg font-bold mb-4 pb-2 border-b border-slate-100">Instructions</h3>
                    <ol className="space-y-4">
                      {recipeDetails.instructions.map((stepStr, index) => (
                        <li key={index} className="flex gap-4 items-start">
                          <span className="flex-shrink-0 h-6 w-6 bg-indigo-50 text-indigo-600 rounded-full flex items-center justify-center text-xs font-bold mt-0.5">
                            {index + 1}
                          </span>
                          <p className="text-sm text-slate-600 leading-relaxed">{stepStr}</p>
                        </li>
                      ))}
                    </ol>
                  </div>

                  {/* Chef Insider Pro-Tip */}
                  <div className="bg-amber-50/60 border border-amber-200/80 p-5 rounded-2xl">
                    <h4 className="text-amber-800 font-bold text-sm uppercase tracking-wider mb-1 flex items-center gap-1.5">
                      ⭐ Chef Pro-Tip
                    </h4>
                    <p className="text-amber-900 text-sm leading-relaxed">{recipeDetails.chef_pro_tip}</p>
                  </div>

                  {/* YouTube Interactive Player Frame */}
                  <div className="bg-white border border-slate-200 p-6 rounded-2xl shadow-sm">
                    <h3 className="text-lg font-bold mb-3 flex items-center gap-2">
                      <Play className="h-5 w-5 text-red-600 fill-red-600" /> Watch Recipe Tutorial
                    </h3>
                    <div className="aspect-video w-full rounded-xl overflow-hidden border border-slate-200 shadow-sm bg-slate-900">
                      <iframe 
                        className="w-full h-full"
                        src={mediaLinks?.youtube_embed_url} 
                        title="YouTube Recipe Video Player"
                        allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" 
                        allowFullScreen
                      />
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default App;