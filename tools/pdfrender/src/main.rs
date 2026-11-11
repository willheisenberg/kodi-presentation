//! Rendert PDF-Seiten als PNG, mit derselben Aufrufform wie `deckcraft-cli`.
//!
//! Zwei Unterbefehle:
//!
//! ```text
//! pdfrender info   <datei.pdf>                      Seitenzahl und Seitengröße als JSON
//! pdfrender render <datei.pdf> (--scale S | --width PX) ZIELORDNER
//! ```
//!
//! `--scale` ist wie bei DeckCraft in Pixeln je Punkt zu verstehen: 2 macht aus
//! einer 960×540-Punkte-Seite ein Bild mit 1920×1080 Pixeln. `--width` gibt
//! stattdessen die Zielbreite in Pixeln vor -- unabhängig davon, wie groß die
//! Seiten des PDFs gesetzt sind. Für einen Fernseher ist das die richtige
//! Angabe: ein Deck mit 1440 Punkten Breite füllt den Cache sonst mit Bildern,
//! die viermal mehr Pixel haben, als der Bildschirm zeigen kann.
use std::process::ExitCode;

use hayro::hayro_interpret::InterpreterSettings;
use hayro::hayro_syntax::Pdf;
use hayro::vello_cpu::color::palette::css::WHITE;
use hayro::{PixmapSettings, RenderCache, RenderSettings, render};

fn main() -> ExitCode {
    let args: Vec<String> = std::env::args().skip(1).collect();
    let ergebnis = match args.first().map(String::as_str) {
        Some("info") => info(&args[1..]),
        Some("render") => rendere(&args[1..]),
        Some("--version") => {
            println!("pdfrender {}", env!("CARGO_PKG_VERSION"));
            Ok(())
        }
        _ => Err(format!(
            "usage:\n  pdfrender info   <datei.pdf>\n  \
             pdfrender render <datei.pdf> --scale S ZIELORDNER\n  pdfrender --version"
        )),
    };
    match ergebnis {
        Ok(()) => ExitCode::SUCCESS,
        Err(e) => {
            eprintln!("pdfrender: {e}");
            ExitCode::FAILURE
        }
    }
}

fn lade(pfad: &str) -> Result<Pdf, String> {
    let roh = std::fs::read(pfad).map_err(|e| format!("{pfad}: {e}"))?;
    // Verschlüsselte PDFs kann hayro nicht öffnen; das meldet Pdf::new.
    Pdf::new(roh).map_err(|e| format!("{pfad}: kein lesbares PDF ({e:?})"))
}

fn info(args: &[String]) -> Result<(), String> {
    let pfad = args.first().ok_or("info: Datei fehlt")?;
    let pdf = lade(pfad)?;
    let seiten = pdf.pages();
    let (breite, hoehe) = seiten
        .first()
        .map(|s| s.render_dimensions())
        .unwrap_or((0.0, 0.0));
    println!(
        "{{\"seiten\":{},\"breitePt\":{:.2},\"hoehePt\":{:.2}}}",
        seiten.len(),
        breite,
        hoehe
    );
    Ok(())
}

fn rendere(args: &[String]) -> Result<(), String> {
    let mut pfad: Option<&str> = None;
    let mut ziel: Option<&str> = None;
    let mut skalierung: f32 = 2.0;
    let mut zielbreite: Option<f32> = None;
    let mut i = 0;
    while i < args.len() {
        match args[i].as_str() {
            "--width" => {
                i += 1;
                zielbreite = Some(
                    args.get(i)
                        .ok_or("--width ohne Wert")?
                        .parse()
                        .map_err(|_| "--width ist keine Zahl".to_string())?,
                );
            }
            "--scale" => {
                i += 1;
                skalierung = args
                    .get(i)
                    .ok_or("--scale ohne Wert")?
                    .parse()
                    .map_err(|_| "--scale ist keine Zahl".to_string())?;
            }
            sonst if pfad.is_none() => pfad = Some(sonst),
            sonst => ziel = Some(sonst),
        }
        i += 1;
    }
    let pfad = pfad.ok_or("render: Datei fehlt")?;
    let ziel = ziel.ok_or("render: Zielordner fehlt")?;
    if !(0.05..=10.0).contains(&skalierung) {
        return Err(format!("--scale {skalierung} liegt ausserhalb 0.05..10"));
    }
    std::fs::create_dir_all(ziel).map_err(|e| format!("{ziel}: {e}"))?;

    let pdf = lade(pfad)?;

    // --width schlaegt --scale: der Maßstab ergibt sich aus der ersten Seite,
    // damit jede Folie dieselbe Breite bekommt, egal wie das PDF gesetzt ist.
    if let Some(breite_px) = zielbreite {
        let seitenbreite = pdf
            .pages()
            .first()
            .map(|s| s.render_dimensions().0)
            .unwrap_or(0.0);
        if seitenbreite <= 0.0 {
            return Err("Seitenbreite unbekannt".to_string());
        }
        skalierung = (breite_px / seitenbreite).clamp(0.05, 10.0);
    }
    // Standardschriften bringt hayro über das Merkmal "embed-fonts" selbst mit;
    // auf LibreELEC gibt es praktisch keine Systemschriften.
    let interpreter = InterpreterSettings::default();
    let qualitaet = RenderSettings::default();
    let pixmap_einstellungen = PixmapSettings {
        x_scale: skalierung,
        y_scale: skalierung,
        bg_color: WHITE,
    };
    let cache = RenderCache::new();

    for (nummer, seite) in pdf.pages().iter().enumerate() {
        let pixmap = render(seite, &cache, &interpreter, &qualitaet, &pixmap_einstellungen);
        let name = format!("{ziel}/slide-{:02}.png", nummer + 1);
        let png = pixmap
            .into_png()
            .map_err(|e| format!("Seite {}: PNG fehlgeschlagen ({e})", nummer + 1))?;
        std::fs::write(&name, png).map_err(|e| format!("{name}: {e}"))?;
        println!("{name}");
    }
    Ok(())
}
