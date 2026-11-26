import React, { useEffect, useRef, useState } from 'react';
import { postJson } from './api.js';
import { beginFlow, isActiveFlow } from './requestFlow.js';
import { recipeOrigin, prepLabel, difficultyLabel } from './recipeUi.js';
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
  const [viewedRecipes, setViewedRecipes] = useState([]);
  const [isSaved, setIsSaved] = useState(false);
  const [isTried, setIsTried] = useState(false);
  const [token, setToken] = useState(() => localStorage.getItem('recipe_profile_token') || '');
  const [profile, setProfile] = useState(null);
  const [usernameInput, setUsernameInput] = useState('');
  const [passwordInput, setPasswordInput] = useState('');
  const [recoveryInput, setRecoveryInput] = useState('');
  const [recoveryCode, setRecoveryCode] = useState('');
  const [authMode, setAuthMode] = useState('signin');
  const [upgrading, setUpgrading] = useState(false);
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
  const [actionPending, setActionPending] = useState(false);
  const [recipeReturnView, setRecipeReturnView] = useState("cuisines");
  const [historyError, setHistoryError] = useState(null);
  const menuFlowRef = useRef({ id: 0, controller: null, pending: false, cuisine: '' });
  const recipeFlowRef = useRef({ id: 0, controller: null });

  const startMenuFlow = (cuisine) => {
    recipeFlowRef.current.controller?.abort();
    recipeFlowRef.current = { id: recipeFlowRef.current.id + 1, controller: null };
    const flow = beginFlow(menuFlowRef.current, cuisine);
    menuFlowRef.current = flow;
    return flow;
  };

  const isCurrentMenuFlow = flow => isActiveFlow(menuFlowRef.current, flow);
  const isCurrentRecipeFlow = flow => isActiveFlow(recipeFlowRef.current, flow);


  const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

  const fetchJson = (path, payload, anonymous = false, signal) => postJson(
    `${API_BASE_URL}${path}`, payload,
    { token: anonymous ? '' : token, signal, timeoutMs: 100000 },
  );

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

  const continueAsGuest = async () => {
    if (loggingIn) return;
    setLoginError(null);
    setLoggingIn(true);
    try {
      const data = await fetchJson('/api/guest-session', {}, true);
      if (!data.token || !data.user_id || data.username !== 'Guest User' ||
          data.account_type !== 'guest') {
        throw new Error('Invalid guest session response');
      }
      menuFlowRef.current.controller?.abort();
      recipeFlowRef.current.controller?.abort();
      menuFlowRef.current = { id: menuFlowRef.current.id + 1, controller: null, pending: false, cuisine: '' };
      recipeFlowRef.current = { id: recipeFlowRef.current.id + 1, controller: null };
      localStorage.setItem('recipe_profile_token', data.token);
      setToken(data.token);
      setProfile({ username: 'Guest User', user_id: data.user_id, account_type: 'guest' });
      setUsernameInput('');
      setPasswordInput('');
      setSelectedCuisine('');
      setSelectedDiet([]);
      setMenuOptions([]);
      setTriedFavorites([]);
      setSavedFavorites([]);
      setViewedRecipes([]);
      setRecipeDetails(null);
      setMediaLinks(null);
      setCurrentView('cuisines');
    } catch (error) {
      setLoginError(error instanceof Error ? error.message : 'Guest access is temporarily unavailable.');
    } finally {
      setLoggingIn(false);
    }
  };

  const login = async event => {
    event.preventDefault();
    if (loggingIn) return;
    setLoginError(null);
    setLoggingIn(true);
    try {
      const username = usernameInput.trim();
      if (authMode === 'recover') {
        const data = await fetchJson('/api/auth/recover',
          { username, password: passwordInput, recovery_code: recoveryInput }, true);
        if (!data.ok || !data.recovery_code) throw new Error('Invalid recovery response');
        setRecoveryCode(data.recovery_code);
        setRecoveryInput('');
        setPasswordInput('');
        setAuthMode('signin');
        return;
      }
      const path = authMode === 'signup' ? '/api/auth/register' : '/api/auth/login';
      const payload = { username, password: passwordInput };
      const data = await fetchJson(path, payload, !upgrading);
      if (!data.token || !data.username || !data.user_id) throw new Error('Invalid account response');
      menuFlowRef.current.controller?.abort();
      recipeFlowRef.current.controller?.abort();
      localStorage.setItem('recipe_profile_token', data.token);
      setToken(data.token);
      setProfile({ username: data.username, user_id: data.user_id,
        account_type: data.account_type || 'guest' });
      setPasswordInput('');
      setUpgrading(false);
      setAuthMode('signin');
      if (data.recovery_code) setRecoveryCode(data.recovery_code);
      setCurrentView('cuisines');
    } catch (error) {
      setLoginError(error instanceof Error ? error.message : 'Could not authenticate.');
    } finally {
      setLoggingIn(false);
    }
  };

  const logout = async () => {
    menuFlowRef.current.controller?.abort();
    recipeFlowRef.current.controller?.abort();
    menuFlowRef.current = { id: menuFlowRef.current.id + 1, controller: null, pending: false, cuisine: '' };
    recipeFlowRef.current = { id: recipeFlowRef.current.id + 1, controller: null };
    if (token) {
      fetch(`${API_BASE_URL}/api/session`, {
        method: 'DELETE', headers: { Authorization: `Bearer ${token}` },
      }).catch(() => {});
    }
    localStorage.removeItem('recipe_profile_token');
    setToken('');
    setProfile(null);
    setUsernameInput('');
    setPasswordInput('');
    setRecoveryInput('');
    setRecoveryCode('');
    setUpgrading(false);
    setAuthMode('signin');
    setSelectedCuisine('');
    setMenuOptions([]);
    setTriedFavorites([]);
    setSavedFavorites([]);
    setViewedRecipes([]);
    setRecipeDetails(null);
    setMediaLinks(null);
    setLoading(false);
    setMenuError(null);
    setRecipeError(null);
    setHistoryError(null);
    setRecipeReturnView('cuisines');
    setActionPending(false);
    setCurrentView('cuisines');
  };

  const updateRecipeAction = async (action, active) => {
    if (actionPending) return;
    setActionPending(true);
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
    } finally {
      setActionPending(false);
    }
  };

  const toggleDietary = (diet) => {
    setSelectedDiet(prev => 
      prev.includes(diet) ? prev.filter(d => d !== diet) : [...prev, diet]
    );
  };

  const refreshDashboardHistory = async (cuisineName, flow) => {
    try {
      const data = await fetchJson('/api/menu-dashboard', {
        cuisine: cuisineName,
        dietary_restrictions: selectedDiet,
      }, false, flow?.controller.signal);
      if (flow && !isCurrentMenuFlow(flow)) return false;
      const favorites = Array.isArray(data.previously_tried) ? data.previously_tried : [];
      const saved = Array.isArray(data.saved_favorites) ? data.saved_favorites : [];
      const viewed = Array.isArray(data.viewed_recipes) ? data.viewed_recipes : [];
      setHistoryError(null);
      setTriedFavorites(favorites);
      setSavedFavorites(saved);
      setViewedRecipes(viewed);
      return favorites.length > 0 || saved.length > 0 || viewed.length > 0;
    } catch (err) {
      if (flow && !isCurrentMenuFlow(flow)) return false;
      if (flow?.controller.signal.aborted) return false;
      console.error('Error refreshing dashboard state:', err);
      setHistoryError('Could not load previous recipes. You can still generate a fresh menu.');
      setTriedFavorites([]);
      setSavedFavorites([]);
      setViewedRecipes([]);
      return false;
    }
  };

  const handleCuisineSelect = async (cuisine) => {
    if (menuFlowRef.current.pending && menuFlowRef.current.cuisine === cuisine) return;
    const flow = startMenuFlow(cuisine);
    setSelectedCuisine(cuisine);
    setLoading(true);
    setMenuError(null);
    try {
      const hasHistory = await refreshDashboardHistory(cuisine, flow);
      if (!isCurrentMenuFlow(flow) || flow.controller.signal.aborted) return;
      if (hasHistory) {
        setMenuOptions([]);
        setCurrentView('dashboard');
      } else {
        await triggerAiMenuGeneration(cuisine, flow);
      }
    } finally {
      if (isCurrentMenuFlow(flow)) {
        flow.pending = false;
        setLoading(false);
      }
    }
  };

  const triggerAiMenuGeneration = async (cuisineName, existingFlow = null) => {
    if (!existingFlow && menuFlowRef.current.pending && menuFlowRef.current.cuisine === cuisineName) return;
    const flow = existingFlow || startMenuFlow(cuisineName);
    setLoading(true);
    setMenuError(null);
    setMenuOptions([]);
    setCurrentView('menu_options');
    try {
      const data = await fetchJson('/api/menu', {
        cuisine: cuisineName,
        dietary_restrictions: selectedDiet,
      }, false, flow.controller.signal);
      if (!isCurrentMenuFlow(flow) || flow.controller.signal.aborted) return;
      if (!Array.isArray(data.menu_options) || data.menu_options.length !== 5) {
        throw new Error('The server returned an incomplete menu. Please retry.');
      }
      setMenuOptions(data.menu_options);
    } catch (err) {
      if (!isCurrentMenuFlow(flow) || flow.controller.signal.aborted) return;
      console.error('Error fetching menu options:', err);
      setMenuError(err instanceof Error ? err.message : 'Unable to load menu suggestions.');
    } finally {
      if (isCurrentMenuFlow(flow)) {
        flow.pending = false;
        setLoading(false);
      }
    }
  };

  const fetchRecipe = async (dishName, restrictions = selectedDiet) => {
    setRecipeReturnView(previous => recipeOrigin(currentView, previous));
    if (recipeFlowRef.current.controller && selectedDish === dishName && loading) return;
    menuFlowRef.current.controller?.abort();
    menuFlowRef.current = { id: menuFlowRef.current.id + 1, controller: null, pending: false, cuisine: '' };
    recipeFlowRef.current.controller?.abort();
    const flow = beginFlow(recipeFlowRef.current);
    recipeFlowRef.current = flow;
    setSelectedDish(dishName);
    setRecipeRestrictions([...restrictions]);
    setRecipeDetails(null);
    setMediaLinks(null);
    setRecipeError(null);
    setActionError(null);
    setActionPending(false);
    setIsSaved(false);
    setIsTried(false);
    setLoading(true);
    setCurrentView('recipe');
    try {
      const data = await fetchJson('/api/recipe', {
        selected_dish: dishName,
        dietary_restrictions: restrictions,
        cuisine: selectedCuisine,
      }, false, flow.controller.signal);
      if (!isCurrentRecipeFlow(flow) || flow.controller.signal.aborted) return;
      if (!data.recipe_details || !Array.isArray(data.recipe_details.ingredients) ||
          !Array.isArray(data.recipe_details.instructions)) {
        throw new Error('The server returned incomplete recipe details. Please retry.');
      }
      setRecipeDetails(data.recipe_details);
      setMediaLinks(data.media_links);
      setIsSaved(Boolean(data.is_saved));
      setIsTried(Boolean(data.is_tried));
    } catch (err) {
      if (!isCurrentRecipeFlow(flow) || flow.controller.signal.aborted) return;
      console.error('Error fetching recipe details:', err);
      setRecipeError(err instanceof Error ? err.message : 'Unable to load this recipe.');
    } finally {
      if (isCurrentRecipeFlow(flow)) {
        recipeFlowRef.current.controller = null;
        setLoading(false);
      }
    }
  };

  const backFromRecipe = () => {
    // Invalidate a pending recipe request before navigating.
    recipeFlowRef.current.controller?.abort();
    recipeFlowRef.current = { id: recipeFlowRef.current.id + 1, controller: null };
    setLoading(false);
    setRecipeError(null);
    setActionError(null);
    const destination = recipeOrigin('recipe', recipeReturnView);
    setCurrentView(destination);
    // History refresh is useful from the dashboard, but should never
    // redirect an options-page user away from their five options.
    if (destination === 'dashboard') void refreshDashboardHistory(selectedCuisine);
  };

  if (checkingSession) return (
    <div className="mx-auto max-w-lg p-10 text-center text-slate-600">Restoring your profile...</div>
  );

  if (recoveryCode) return (
    <main className="mx-auto max-w-md px-4 py-16">
      <section aria-label="Recovery code" className="space-y-4 rounded-2xl border border-amber-300 p-6">
        <h1 className="text-2xl font-bold">Save your one-time recovery code</h1>
        <p className="text-sm">Keep this in a password manager. It will not be shown again. If you lose it, username-only password recovery is unavailable.</p>
        <code className="block break-all rounded-lg bg-slate-100 p-3 select-all">{recoveryCode}</code>
        <button type="button" onClick={() => setRecoveryCode('')}
          className="w-full rounded-lg bg-indigo-600 p-3 font-semibold text-white">I have saved my code</button>
      </section>
    </main>
  );

  if (!profile || upgrading) return (
    <main className="mx-auto max-w-md px-4 py-16">
      <section className="space-y-4 rounded-3xl border border-slate-200 bg-white p-8 shadow-sm">
        <h1 className="text-2xl font-extrabold text-indigo-700">What Should I Eat?</h1>
        <h2 className="text-lg font-semibold">{upgrading ? 'Keep your existing recipes'
          : authMode === 'signin' ? 'Sign in' : authMode === 'signup' ? 'Create account'
            : 'Recover account'}</h2>
        <p className="text-sm text-slate-600">{upgrading
          ? 'Your active anonymous session can be upgraded without losing recipe history.'
          : 'Registered accounts restore saved, viewed and tried recipes after signing out.'}</p>
        {!upgrading && <div className="flex flex-wrap gap-2" role="group" aria-label="Sign-in options">
          {[['signin','Sign in'],['signup','Sign up']].map(([id,label]) =>
            <button type="button" key={id} onClick={() => { setAuthMode(id); setLoginError(null); }}
              aria-pressed={authMode === id}
              className={`rounded-lg px-3 py-2 text-sm ${authMode === id ? 'bg-indigo-600 text-white' : 'border border-slate-300'}`}>{label}</button>)}
        </div>}
        <form onSubmit={login} className="space-y-3">
          <label htmlFor="username" className="block text-sm font-semibold">Username</label>
          <input id="username" required autoComplete="username" minLength={3} maxLength={24}
            pattern="[A-Za-z0-9_]{3,24}" value={usernameInput}
            onChange={e => setUsernameInput(e.target.value)}
            className="w-full rounded-lg border border-slate-300 p-3"/>
          <>
            <label htmlFor="password" className="block text-sm font-semibold">
              {authMode === 'recover' ? 'New password' : 'Password'}</label>
            <input id="password" type="password" required minLength={12} maxLength={256}
              autoComplete={authMode === 'signin' ? 'current-password' : 'new-password'}
              value={passwordInput} onChange={e => setPasswordInput(e.target.value)}
              className="w-full rounded-lg border border-slate-300 p-3"/>
          </>
          {authMode === 'recover' && <>
            <label htmlFor="recovery" className="block text-sm font-semibold">Saved recovery code</label>
            <input id="recovery" required autoComplete="off" minLength={32} maxLength={128}
              value={recoveryInput} onChange={e => setRecoveryInput(e.target.value)}
              className="w-full rounded-lg border border-slate-300 p-3"/>
          </>}
          {loginError && <p role="alert" className="text-sm text-red-700">{loginError}</p>}
          <button disabled={loggingIn} type="submit"
            className="w-full rounded-lg bg-indigo-600 p-3 font-semibold text-white disabled:opacity-50">
            {loggingIn ? 'Working…' : upgrading || authMode === 'signup' ? 'Create account'
              : authMode === 'recover' ? 'Reset password'
                : 'Sign in'}
          </button>
        </form>
        {!upgrading && <>
          <div className="flex items-center gap-3 text-xs text-slate-500" aria-hidden="true">
            <span className="h-px flex-1 bg-slate-200"/>or<span className="h-px flex-1 bg-slate-200"/>
          </div>
          <button type="button" onClick={continueAsGuest} disabled={loggingIn}
            className="w-full rounded-lg border-2 border-indigo-200 bg-indigo-50 p-3 font-semibold text-indigo-800 hover:bg-indigo-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 disabled:opacity-50">
            {loggingIn ? 'Starting guest session…' : 'Continue as Guest'}
          </button>
          <p className="text-xs text-slate-600">No name, password, or registration required. Your name will appear as Guest User. Guest history is temporary and cannot be recovered after exit or session expiry.</p>
        </>}
        {authMode === 'signin' && <button type="button" onClick={() => {
          setAuthMode('recover'); setLoginError(null);
        }} className="text-sm text-indigo-700 underline">Reset with a recovery code</button>}
        {upgrading && <button type="button" onClick={() => setUpgrading(false)}
          className="text-sm text-slate-700 underline">Back to recipes</button>}
        <p className="text-xs text-slate-500">Guest profiles cannot be restored after exit or expiry. Account recovery requires the one-time recovery code; email recovery is not available yet.</p>
      </section>
    </main>
  );

  return (
    <div className="max-w-4xl mx-auto min-w-0 px-4 py-8">
      {/* Header Layout */}
      <header className="flex flex-wrap items-center gap-3 mb-10 pb-6 border-b border-slate-200">
        <Utensils className="h-8 w-8 text-indigo-600" />
        <h1 className="min-w-0 flex-1 text-2xl sm:text-3xl font-extrabold tracking-tight bg-gradient-to-r from-indigo-600 to-violet-600 bg-clip-text text-transparent">
          What Should I Eat?
        </h1>
        <div className="ml-auto flex min-w-0 items-center gap-3">
          <span className="max-w-32 truncate text-xs font-semibold text-slate-600" title={profile.account_type === 'guest' ? 'Temporary guest profile' : `@${profile.username}`}>
            {profile.account_type === 'guest' ? 'Guest User' : `@${profile.username}`}</span>
          {profile.account_type !== 'registered' && <button type="button" onClick={() => {
            setUpgrading(true); setAuthMode('signup');
            setUsernameInput(profile.username === 'Guest User' ? '' : profile.username);
            setLoginError(null);
          }} className="rounded-lg border border-indigo-200 px-3 py-2 text-xs text-indigo-700">Keep my recipes</button>}
          <button onClick={logout} className="rounded-lg border border-slate-200 px-3 py-2 text-xs text-slate-600 hover:bg-slate-100">{profile.account_type === 'guest' ? 'Exit Guest' : 'Sign out'}</button>
        </div>
      </header>

      {/* VIEW 1: SELECT CUISINE & PREFERENCES */}
      {currentView === "cuisines" && (
        <div className="space-y-8 animate-fadeIn">
          <div>
            <h2 className="text-xl font-semibold mb-3">Any dietary restrictions?</h2>
            <div role="group" aria-label="Dietary restrictions" className="flex flex-wrap gap-2 sm:gap-3">
              {DIETARY_OPTIONS.map(diet => (
                <button
                  key={diet}
                  type="button"
                  aria-pressed={selectedDiet.includes(diet)}
                  onClick={() => toggleDietary(diet)}
                  className={`min-h-11 px-4 py-2 rounded-full border text-sm font-medium transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 focus-visible:ring-offset-2 ${
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
                  className="min-w-0 p-4 sm:p-6 text-left bg-white border border-slate-200 rounded-xl hover:border-indigo-500 hover:shadow-md transition-all group focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500"
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

          {historyError && <p role="status" className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-800">{historyError}</p>}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {viewedRecipes.length > 0 && (
              <div className="md:col-span-2 rounded-2xl border border-slate-200 bg-slate-50 p-5">
                <h3 className="mb-1 text-sm font-bold text-slate-800">Viewed recipes</h3>
                <p className="mb-3 text-xs text-slate-500">Recipes you opened, whether or not you saved or cooked them.</p>
                <div className="flex flex-wrap gap-2">
                  {viewedRecipes.map((dish, index) => (
                    <button key={index}
                      onClick={() => fetchRecipe(dish.dish_name, dish.dietary_restrictions)}
                      className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-semibold hover:border-indigo-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500">
                      {dish.dish_name}
                    </button>
                  ))}
                </div>
              </div>
            )}
            {savedFavorites.length > 0 && (
              <div className="md:col-span-2 rounded-2xl border border-emerald-100 bg-emerald-50 p-5">
                <h3 className="mb-3 text-sm font-bold text-emerald-800">Saved recipes</h3>
                <div className="flex flex-wrap gap-2">
                  {savedFavorites.map((dish, index) => (
                    <button key={index} onClick={() => fetchRecipe(dish.dish_name, dish.dietary_restrictions)}
                      className="rounded-lg border border-emerald-200 bg-white px-3 py-2 text-xs font-semibold hover:border-emerald-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500">
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
                  <button
                    type="button"
                    key={i}
                    onClick={() => fetchRecipe(dish.dish_name, dish.dietary_restrictions)}
                    className="group block w-full min-w-0 rounded-xl border border-slate-100 bg-white p-4 text-left shadow-2xs transition-all hover:border-indigo-500 hover:shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 focus-visible:ring-offset-2"
                  >
                    <div className="flex min-w-0 flex-wrap items-start gap-2">
                      <h4 className="min-w-0 flex-1 break-words text-sm font-bold text-slate-800 group-hover:text-indigo-600">{dish.dish_name}</h4>
                      <span className="inline-flex w-fit shrink-0 items-center rounded bg-emerald-50 px-2 py-0.5 text-[10px] font-bold text-emerald-700">Cached</span>
                    </div>
                    {dish.teaser && <p className="mt-1 line-clamp-2 break-words text-xs leading-relaxed text-slate-500">{dish.teaser}</p>}
                    <div className="mt-3 flex min-w-0 flex-wrap items-start gap-2 border-t border-slate-100 pt-2">
                      <span className="min-w-0 flex-1 break-words text-[11px] leading-relaxed text-slate-500">
                        <span className="font-semibold">Prep:</span> {prepLabel(dish.prep_time)}
                      </span>
                      <span className="inline-flex h-fit w-fit shrink-0 rounded-full bg-slate-100 px-2 py-1 text-[10px] font-bold capitalize text-slate-600">
                        {difficultyLabel(dish.difficulty)}
                      </span>
                    </div>
                  </button>
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
                    disabled={loading}
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
                    <button
                      type="button"
                      key={idx}
                      onClick={() => fetchRecipe(dish.dish_name)}
                      className="w-full min-w-0 p-3.5 text-left bg-white border border-slate-100 rounded-xl hover:border-amber-500 hover:shadow-xs transition-all flex justify-between items-center group focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-500 focus-visible:ring-offset-2"
                    >
                      <div className="min-w-0 flex-1 space-y-0.5 pr-2">
                        <h4 className="text-xs font-bold text-slate-800 group-hover:text-amber-600 transition-colors">{dish.dish_name}</h4>
                        <p className="text-slate-500 text-[11px] line-clamp-1 leading-normal">{dish.teaser}</p>
                      </div>
                      <ChevronRight className="h-3 w-3 text-slate-300 group-hover:text-amber-500 transform group-hover:translate-x-0.5 transition-all flex-shrink-0" />
                    </button>
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
            onClick={() => setCurrentView(triedFavorites.length > 0 || savedFavorites.length > 0 || viewedRecipes.length > 0 ? "dashboard" : "cuisines")}
            className="flex items-center gap-2 text-sm font-medium text-slate-500 hover:text-slate-800 transition-colors"
          >
            <ArrowLeft className="h-4 w-4" /> Back
          </button>
          
          <h2 className="text-2xl font-bold">5 Handpicked {selectedCuisine} Options</h2>

          {loading ? (
            <div className="space-y-3" role="status" aria-label="Loading menu recommendations">
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
                <button
                  type="button"
                  key={idx}
                  onClick={() => fetchRecipe(dish.dish_name)}
                  className="w-full min-w-0 p-5 text-left bg-white border border-slate-200 rounded-xl hover:border-indigo-500 hover:shadow-sm transition-all flex justify-between items-center group focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 focus-visible:ring-offset-2"
                >
                  <div className="min-w-0 flex-1 space-y-1 pr-3">
                    <h3 className="text-lg font-bold group-hover:text-indigo-600 transition-colors">{dish.dish_name}</h3>
                    <p className="text-slate-600 text-sm leading-relaxed">{dish.teaser}</p>
                    <span className="inline-block bg-slate-100 text-slate-600 text-xs px-2 py-0.5 rounded font-medium">
                      Protein Base: {dish.primary_protein}
                    </span>
                  </div>
                  <ChevronRight className="h-5 w-5 shrink-0 text-slate-300 group-hover:text-indigo-500 transform group-hover:translate-x-1 transition-all" />
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      {/* VIEW 3: FULL RECIPE DETAILS & RICH MEDIA ASSISTANT */}
      {currentView === "recipe" && (
        <div className="space-y-6 animate-fadeIn">
          <button 
            onClick={backFromRecipe}
            className="flex items-center gap-2 rounded text-sm font-medium text-slate-500 hover:text-slate-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500"
          >
            <ArrowLeft className="h-4 w-4" /> {recipeReturnView === 'menu_options' ? 'Back to Recipe Options' : recipeReturnView === 'dashboard' ? 'Back to Menu Dashboard' : 'Back to Cuisines'}
          </button>

          {loading ? (
            <div className="space-y-4 animate-pulse" role="status" aria-label="Loading recipe details">
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
                  disabled={actionPending} aria-pressed={isSaved}
                  className={`rounded-xl border px-4 py-2 text-sm font-semibold focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 disabled:opacity-60 ${isSaved ? 'border-emerald-600 bg-emerald-50 text-emerald-800' : 'border-slate-200 bg-white text-slate-700'}`}>
                  {isSaved ? 'Saved ✓ · Unsave' : '☆ Save recipe'}
                </button>
                <button type="button" onClick={() => updateRecipeAction('tried', !isTried)}
                  disabled={actionPending} aria-pressed={isTried}
                  className={`rounded-xl border px-4 py-2 text-sm font-semibold focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 disabled:opacity-60 ${isTried ? 'border-indigo-600 bg-indigo-50 text-indigo-800' : 'border-slate-200 bg-white text-slate-700'}`}>
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
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 p-4 bg-white border border-slate-200 rounded-xl text-center shadow-sm">
                <div className="flex min-w-0 flex-col items-center gap-1 sm:border-r border-slate-100">
                  <Clock className="h-5 w-5 text-indigo-500" />
                  <span className="text-xs text-slate-400 font-medium uppercase tracking-wider">Prep Time</span>
                  <span className="max-w-full break-words text-sm font-semibold">{recipeDetails.prep_time}</span>
                </div>
                <div className="flex min-w-0 flex-col items-center gap-1 sm:border-r border-slate-100">
                  <Flame className="h-5 w-5 text-orange-500" />
                  <span className="text-xs text-slate-400 font-medium uppercase tracking-wider">Cook Time</span>
                  <span className="max-w-full break-words text-sm font-semibold">{recipeDetails.cook_time}</span>
                </div>
                <div className="flex min-w-0 flex-col items-center gap-1">
                  <Users className="h-5 w-5 text-emerald-500" />
                  <span className="text-xs text-slate-400 font-medium uppercase tracking-wider">Servings</span>
                  <span className="max-w-full break-words text-sm font-semibold">{recipeDetails.servings}</span>
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