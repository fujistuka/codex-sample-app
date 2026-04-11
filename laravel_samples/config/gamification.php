<?php

return [
    'base_xp' => 10,
    'level' => [
        'xp_per_level' => 100,
    ],
    'streak_bonus' => [
        30 => 20,
        7 => 10,
        3 => 5,
    ],
    'streak_multiplier' => [
        ['min' => 30, 'max' => null, 'multiplier' => 1.5],
        ['min' => 7, 'max' => 29, 'multiplier' => 1.2],
        ['min' => 3, 'max' => 6, 'multiplier' => 1.1],
        ['min' => 1, 'max' => 2, 'multiplier' => 1.0],
    ],
];
