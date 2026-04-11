Human only notes, do not modify


- wondered how the autonomous workflow would do on a more sophisticated problem, optimizing a model to play chrome dino
- challenging because it runs in the browser, pace changes, etc.
- immediately jumped to a more sophisticated solution
- first pass failed on classic newbie mistake in ML: train env doesn't match the inference env (used headless to speed up training but headless != browser with selenium driver)
- it accepted this! tried to brush it off! indicates flaw in the autonomous template, need to revise
- after I told it the browser validation IS the test, it realized the mistake above and came up with strategies to fix it
- took several hours iterating for it to figure out what the real problem was (headless env simulated without a cap on jump height, but browser limits to 87 px)
- trained a third version with the headless env fixes 