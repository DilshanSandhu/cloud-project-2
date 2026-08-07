const SUPABASE_URL = "https://zlunexroeirffgoyxwpc.supabase.co";
const SUPABASE_KEY = "sb_publishable_Kv2CzJhA1veAlvJ1HGf_WQ_vvSKKhGd";

window.supabaseClient = supabase.createClient(
    SUPABASE_URL,
    SUPABASE_KEY,
    {
        auth: {
            persistSession: true,
            autoRefreshToken: true,
            detectSessionInUrl: true
        }
    }
);
