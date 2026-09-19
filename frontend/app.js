// Feature detect 'commandForElement' on HTMLButtonElement.prototype.
// Conditionally load the invokers-polyfill from a CDN only in browsers lacking native support.
if (!('commandForElement' in HTMLButtonElement.prototype)) {
  import('https://esm.run/invokers-polyfill');
}

// Feature detect 'popover' on HTMLElement.prototype.
if (!("popover" in HTMLElement.prototype)) {
  import("https://unpkg.com/@oddbird/popover-polyfill@latest/dist/popover.min.js");
}

// Initialize any additional interactive behaviors
document.addEventListener('DOMContentLoaded', () => {
    // Optionally handle form submissions if needed
    document.getElementById('upload-form').addEventListener('submit', (e) => {
        e.preventDefault();
        console.log("Document uploaded!");
        const dialog = document.getElementById('upload-dialog');
        if (dialog) dialog.close();
    });

    document.getElementById('ontology-form').addEventListener('submit', (e) => {
        e.preventDefault();
        console.log("Ontology created!");
        const dialog = document.getElementById('ontology-dialog');
        if (dialog) dialog.close();
    });
});
